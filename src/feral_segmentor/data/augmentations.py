import abc
from pathlib import Path
from typing import Any, Callable

import hydra
import numpy as np
from omegaconf import DictConfig

from feral_segmentor import constants as C
from feral_segmentor.config.store import register_configs
from feral_segmentor.utils import get_logger

log = get_logger(__name__)


class Augmentation(abc.ABC):
    """Composes via constructor chaining: Outer(Inner()).augment(x) == Outer._apply(Inner._apply(x))."""

    def __init__(self, inner: "Augmentation | None" = None):
        self.inner = inner

    def augment(self, sample: Any) -> Any:
        if self.inner is not None:
            sample = self.inner.augment(sample)
        return self._apply(sample)

    @abc.abstractmethod
    def _apply(self, sample: Any) -> Any: ...

    def _own_params(self) -> dict[str, str | float]:
        return {}

    def to_params(self, index: int = 0) -> dict[str, str | float]:
        flat = {
            f"{index}.{type(self).__name__}.{k}": v
            for k, v in self._own_params().items()
        }
        if self.inner is not None:
            flat |= self.inner.to_params(index=index + 1)
        return flat

    def variant_label(self) -> str:
        names = [type(self).__name__]
        if self.inner is not None:
            names.insert(0, self.inner.variant_label())
        return "_".join(names)


class FunctionAugmentation(Augmentation):
    """Adapter wrapping an albumentations/torchvision-style transform callable."""

    def __init__(self, fn: Callable, inner: "Augmentation | None" = None, **kwargs):
        super().__init__(inner)
        self.fn = fn
        self.kwargs = kwargs

    def _apply(self, sample: Any) -> Any:
        raise NotImplementedError(
            "backend call convention not yet chosen (albumentations vs torchvision)"
        )

    def _own_params(self) -> dict[str, str | float]:
        return {"fn": type(self.fn).__name__, **self.kwargs}


# --- Concrete augmentations -------------------------------------------------
# A *sample* is a numpy ndarray image of shape (H, W) or (H, W, C). Each
# concrete ``_apply`` is pure and deterministic (no RNG state), so a given
# input always maps to the same output — i.e. trivially seedable/reproducible.


class Identity(Augmentation):
    """No-op augmentation; returns the sample unchanged. Used for empty chains."""

    def _apply(self, sample: Any) -> Any:
        return sample


class HorizontalFlip(Augmentation):
    """Mirror the image left-to-right (flip along the width axis)."""

    def _apply(self, sample: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(np.flip(sample, axis=1))


class RandomRotate90(Augmentation):
    """Rotate by a fixed multiple of 90 degrees (deterministic given ``k``)."""

    def __init__(
        self, inner: "Augmentation | None" = None, k: int = C.DEFAULT_ROTATE90_K
    ):
        super().__init__(inner)
        self.k = k

    def _apply(self, sample: np.ndarray) -> np.ndarray:
        return np.ascontiguousarray(np.rot90(sample, k=self.k, axes=(0, 1)))

    def _own_params(self) -> dict[str, str | float]:
        return {"k": self.k}


class BrightnessShift(Augmentation):
    """Add a constant offset, clipping to the valid [0, 1] range."""

    def __init__(
        self,
        inner: "Augmentation | None" = None,
        shift: float = C.DEFAULT_BRIGHTNESS_SHIFT,
    ):
        super().__init__(inner)
        self.shift = shift

    def _apply(self, sample: np.ndarray) -> np.ndarray:
        return np.clip(sample.astype(np.float64) + self.shift, 0.0, 1.0)

    def _own_params(self) -> dict[str, str | float]:
        return {"shift": self.shift}


class GammaAdjust(Augmentation):
    """Apply gamma correction ``out = in ** gamma`` on [0, 1] images."""

    def __init__(
        self, inner: "Augmentation | None" = None, gamma: float = C.DEFAULT_GAMMA
    ):
        super().__init__(inner)
        self.gamma = gamma

    def _apply(self, sample: np.ndarray) -> np.ndarray:
        clipped = np.clip(sample.astype(np.float64), 0.0, 1.0)
        return np.power(clipped, self.gamma)

    def _own_params(self) -> dict[str, str | float]:
        return {"gamma": self.gamma}


# --- Registry ---------------------------------------------------------------
_AUGMENTATIONS: dict[str, type[Augmentation]] = {
    "Identity": Identity,
    "HorizontalFlip": HorizontalFlip,
    "RandomRotate90": RandomRotate90,
    "BrightnessShift": BrightnessShift,
    "GammaAdjust": GammaAdjust,
}


def build_chain(cfg: DictConfig) -> Augmentation:
    """Construct a nested augmentation chain from ``cfg.ops``.

    ``cfg`` is an :class:`AugmentationConfig`-shaped node (a DictConfig with an
    ``ops: list[str]``). The first name in ``ops`` becomes the *innermost*
    augmentation (applied first), composed outward via the ``inner=`` pattern.
    An empty ``ops`` yields an :class:`Identity` no-op.
    """
    ops = list(cfg.ops) if cfg.ops is not None else []
    if not ops:
        return Identity()
    chain: Augmentation | None = None
    for name in ops:
        try:
            cls = _AUGMENTATIONS[name]
        except KeyError as exc:
            raise KeyError(
                f"unknown augmentation op {name!r}; registered: {sorted(_AUGMENTATIONS)}"
            ) from exc
        chain = cls(inner=chain)
    assert chain is not None  # guaranteed: ops is non-empty
    return chain


def run_augment_stage(cfg: DictConfig) -> None:
    """Build the chain and apply it across data/raw -> data/augmented.

    IO is guarded: if the input directory is absent we just log and return, so
    the stage never crashes in environments where data has not been fetched.
    """
    chain = build_chain(cfg.augmentation)
    log.info("built augmentation chain: %s", chain.variant_label())

    raw_dir = (
        Path(getattr(cfg.data, "root", "data")) / "raw"
        if "data" in cfg
        else Path("data/raw")
    )
    out_dir = (
        Path(getattr(cfg.data, "root", "data")) / "augmented"
        if "data" in cfg
        else Path("data/augmented")
    )

    if not raw_dir.exists():
        log.info("raw dir %s absent; nothing to augment", raw_dir)
        return

    out_dir.mkdir(parents=True, exist_ok=True)
    import cv2

    suffixes = {".png", ".jpg", ".jpeg", ".bmp"}
    for path in sorted(raw_dir.rglob("*")):
        if path.suffix.lower() not in suffixes:
            continue
        image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
        if image is None:
            log.warning("could not read %s; skipping", path)
            continue
        normalized = image.astype(np.float64) / 255.0
        augmented = chain.augment(normalized)
        out_image = np.clip(augmented * 255.0, 0, 255).astype(np.uint8)
        dest = out_dir / f"{path.stem}_{chain.variant_label()}{path.suffix}"
        cv2.imwrite(str(dest), out_image)
        log.info("wrote %s", dest)


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    register_configs()
    run_augment_stage(cfg)


if __name__ == "__main__":
    main()
