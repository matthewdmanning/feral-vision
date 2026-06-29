"""Dataset creator for the feral-segmentor pipeline.

Canonical dataset layout on disk:
    <root>/images/          raw image files
    <root>/annotations/     annotation files (masks, YOLO .txt, JSON, etc.)

Key design decisions:
- Image is a path reference; pixels are never loaded until needed.
- Augmentation (albumentations) and merging are mutually exclusive per dataset.
- Lazy mode pre-generates sample order + per-sample aug seed at init; pixel I/O
  deferred to __getitem__. Eager mode writes augmented images to out_dir at init.
- Source image paths must be disjoint across merged datasets (checked at init).
- size: int = absolute count, float = fraction of dataset; seed=42 default.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from feral_segmentor.data.annotations import (
    BBoxAnnotation,
    ClassificationAnnotation,
    MaskAnnotation,
)
from feral_segmentor.models.register_model import load_model_registry
from feral_segmentor.tasks import CVTask
from feral_segmentor.utils import get_logger

logger = get_logger(__name__)

_IMAGES_DIR = "images"
_ANNOTATIONS_DIR = "annotations"
_SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass
class Image:
    """Thin path reference to a source image. Pixels loaded on demand."""

    path: Path
    width: int | None = None
    height: int | None = None

    def load(self):
        """Return (H, W, C) numpy array in RGB."""
        import cv2

        img = cv2.imread(str(self.path), cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"failed to read image: {self.path}")
        return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@dataclass
class Sample:
    """One dataset sample: an image reference and its annotation dict."""

    image: Image
    annotations: dict[CVTask, Any] = field(default_factory=dict)
    # Deterministic per-sample aug seed (lazy mode only).
    aug_params: dict[str, Any] | None = None


def _validate_tasks(tasks: list[CVTask]) -> None:
    """Raise ValueError if the task combination is invalid."""
    seg_tasks = {CVTask.SEG_INSTANCE, CVTask.SEG_SEMANTIC} & set(tasks)
    if len(seg_tasks) > 1:
        raise ValueError("SEG_INSTANCE and SEG_SEMANTIC are mutually exclusive")
    if CVTask.DETECTION in tasks and len(tasks) > 1:
        raise ValueError("DETECTION is exclusive with all other tasks")
    if tasks.count(CVTask.POSE) > 1:
        raise ValueError("POSE may appear at most once per dataset")


def _build_compose(tasks: list[CVTask], transforms_cfg: list[dict]):
    """Build albumentations Compose with params derived from task list."""
    import albumentations as A

    bbox_params = None
    additional_targets = {}

    if CVTask.SEG_INSTANCE in tasks:
        bbox_params = A.BboxParams(format="yolo", label_fields=["class_labels"])
    if CVTask.SEG_SEMANTIC in tasks:
        additional_targets["mask"] = "mask"

    transforms = [A.from_dict(t) for t in transforms_cfg]
    return A.Compose(
        transforms,
        bbox_params=bbox_params,
        additional_targets=additional_targets if additional_targets else None,
    )


class FeralDataset:
    """Dataset supporting augmentation or merging (mutually exclusive).

    Parameters
    ----------
    root:
        Dataset root with ``images/`` and ``annotations/`` subdirs.
    tasks:
        Active :class:`CVTask` list. Must be a valid combination.
    size:
        int -> absolute count; float -> fraction; None -> all.
    seed:
        Frozen at init. Default 42.
    lazy:
        True  -> defer pixel I/O; pre-generate per-sample aug seeds.
        False -> write augmented images to ``out_dir`` immediately.
    transforms_cfg:
        Albumentations native transform dicts. Exclusive with ``merged_from``.
    out_dir:
        Output dir for eager augmentation. Required when lazy=False.
    target_model:
        Model name from registry. Derives tasks/annotation_format/image_size.
        Raises KeyError if not registered. Explicit args override profile.
    merged_from:
        Datasets to merge. Source paths must be disjoint. Exclusive with
        ``transforms_cfg``.
    """

    def __init__(
        self,
        root: str | Path | None = None,
        tasks: list[CVTask] | None = None,
        size: int | float | None = None,
        seed: int = 42,
        lazy: bool = True,
        transforms_cfg: list[dict] | None = None,
        out_dir: str | Path | None = None,
        target_model: str | None = None,
        merged_from: list["FeralDataset"] | None = None,
    ) -> None:
        if transforms_cfg and merged_from:
            raise ValueError("transforms_cfg and merged_from are mutually exclusive")

        self.seed: int = seed
        self.lazy = lazy
        self.transforms_cfg = transforms_cfg or []
        self.out_dir = Path(out_dir) if out_dir else None
        self._augmented: list[Path] = []

        if target_model is not None:
            profile = load_model_registry(
                target_model
            )  # KeyError if unknown — fail early
            if tasks is None:
                tasks = list(profile.model_outputs)
            logger.info("target_model=%r tasks=%s", target_model, tasks)

        self.tasks: list[CVTask] = tasks or []
        _validate_tasks(self.tasks)

        if merged_from is not None:
            self.samples = self._merge(merged_from)
            self._compose = None
            return

        if root is None:
            raise ValueError("root is required when not merging")

        self.root = Path(root).resolve()
        self.images_dir = self.root / _IMAGES_DIR
        self.annotations_dir = self.root / _ANNOTATIONS_DIR

        if not self.images_dir.is_dir():
            raise FileNotFoundError(f"images dir not found: {self.images_dir}")

        all_samples = self._index()

        rng = random.Random(self.seed)
        if size is None:
            self.samples = list(all_samples)
        elif isinstance(size, float):
            n = max(1, round(len(all_samples) * size))
            self.samples = rng.sample(all_samples, min(n, len(all_samples)))
        else:
            self.samples = rng.sample(all_samples, min(int(size), len(all_samples)))
        rng.shuffle(self.samples)

        if self.transforms_cfg:
            self._compose = _build_compose(self.tasks, self.transforms_cfg)
            if lazy:
                self._presample_aug_params()
            else:
                if self.out_dir is None:
                    raise ValueError("out_dir required for eager augmentation")
                self._eager_augment()
        else:
            self._compose = None

    # ------------------------------------------------------------------

    def _index(self) -> list[Sample]:
        samples: list[Sample] = []
        for img_path in sorted(self.images_dir.iterdir()):
            if img_path.suffix.lower() not in _SUPPORTED_IMAGE_EXTENSIONS:
                continue
            anns = self._load_annotations(img_path.stem)
            samples.append(Sample(image=Image(path=img_path), annotations=anns))
        if not samples:
            raise FileNotFoundError(f"no images found in {self.images_dir}")
        return samples

    def _load_annotations(self, stem: str) -> dict[CVTask, Any]:
        anns: dict[CVTask, Any] = {}
        d = self.annotations_dir

        if CVTask.SEG_SEMANTIC in self.tasks:
            for ext in (".png", ".jpg"):
                p = d / f"{stem}{ext}"
                if p.exists():
                    anns[CVTask.SEG_SEMANTIC] = MaskAnnotation(path=p)
                    break

        if CVTask.SEG_INSTANCE in self.tasks:
            p = d / f"{stem}.txt"
            if p.exists():
                anns[CVTask.SEG_INSTANCE] = BBoxAnnotation(path=p)

        if CVTask.CLASSIFICATION in self.tasks:
            import json

            p = d / f"{stem}.json"
            if p.exists():
                with p.open() as f:
                    raw = json.load(f)
                anns[CVTask.CLASSIFICATION] = [
                    ClassificationAnnotation(
                        name=k,
                        input_type=v["input_type"],
                        value=v["value"],
                    )
                    for k, v in raw.items()
                ]

        return anns

    def _presample_aug_params(self) -> None:
        rng = random.Random(self.seed)
        for sample in self.samples:
            sample.aug_params = {"seed": rng.randint(0, 2**31)}

    def _eager_augment(self) -> None:
        import cv2

        assert self.out_dir is not None
        self.out_dir.mkdir(parents=True, exist_ok=True)
        for sample in self.samples:
            result = self._run_compose(sample)
            out_path = self.out_dir / sample.image.path.name
            cv2.imwrite(str(out_path), cv2.cvtColor(result["image"], cv2.COLOR_RGB2BGR))
            self._augmented.append(out_path)
        logger.info(
            "eager augmentation: %d images -> %s", len(self._augmented), self.out_dir
        )

    def _merge(self, datasets: list["FeralDataset"]) -> list[Sample]:
        seen: set[Path] = set()
        merged: list[Sample] = []
        for ds in datasets:
            for sample in ds.samples:
                p = sample.image.path.resolve()
                if p in seen:
                    raise ValueError(f"merge rejected: image in multiple datasets: {p}")
                seen.add(p)
                merged.append(sample)
        return merged

    def _run_compose(self, sample: Sample) -> dict:
        assert self._compose is not None
        img = sample.image.load()
        kwargs: dict[str, Any] = {"image": img}

        mask_ann = sample.annotations.get(CVTask.SEG_SEMANTIC)
        if mask_ann is not None:
            mask_ann.load()
            kwargs["mask"] = mask_ann.mask

        bbox_ann = sample.annotations.get(CVTask.SEG_INSTANCE)
        if bbox_ann is not None:
            bbox_ann.load()
            kwargs["bboxes"] = bbox_ann.boxes.tolist()
            kwargs["class_labels"] = bbox_ann.class_ids.tolist()

        return self._compose(**kwargs)

    # ------------------------------------------------------------------

    def apply_augmentation(self, sample: Sample) -> dict:
        """Apply augmentation to one sample. Returns albumentations result dict."""
        if self._compose is None:
            raise RuntimeError("no transforms_cfg set on this dataset")
        return self._run_compose(sample)

    @property
    def source_paths(self) -> set[Path]:
        return {s.image.path.resolve() for s in self.samples}

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Any, dict[CVTask, Any]]:
        sample = self.samples[index]
        if self._compose is not None:
            result = self._run_compose(sample)
            anns: dict[CVTask, Any] = {}
            if "mask" in result:
                anns[CVTask.SEG_SEMANTIC] = result["mask"]
            if "bboxes" in result:
                anns[CVTask.SEG_INSTANCE] = {
                    "bboxes": result["bboxes"],
                    "class_labels": result["class_labels"],
                }
            return result["image"], anns
        else:
            img = sample.image.load()
            anns = {}
            for task, ann in sample.annotations.items():
                anns[task] = ann if isinstance(ann, list) else ann.load()
            return img, anns
