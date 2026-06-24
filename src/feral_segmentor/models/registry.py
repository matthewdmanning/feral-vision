"""Model profile registry and builder.

Each entry in ``_MODEL_PROFILES`` is a :class:`ModelProfile` combining the
``nn.Module`` class with dataset-facing metadata (task list, annotation format,
canonical image size). ``build_model`` and ``get_model`` call-sites unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass

from omegaconf import DictConfig

from feral_segmentor.models.base import SegmentationModel
from feral_segmentor.tasks import CVTask

DEFAULT_ARCH: str = "student"


@dataclass
class ModelProfile:
    """All static metadata for a registered model architecture."""

    arch_cls: type | None  # resolved lazily to avoid circular imports
    tasks: list[CVTask]
    annotation_format: str  # e.g. "mask", "yolo_seg", "yolo_det"
    image_size: int  # canonical square side length


_MODEL_PROFILES: dict[str, ModelProfile] = {
    "student": ModelProfile(
        arch_cls=None,
        tasks=[CVTask.SEG_SEMANTIC],
        annotation_format="mask",
        image_size=256,
    ),
    "teacher": ModelProfile(
        arch_cls=None,
        tasks=[CVTask.SEG_INSTANCE, CVTask.SEG_SEMANTIC],
        annotation_format="yolo_seg",
        image_size=640,
    ),
    "yolo11n-seg": ModelProfile(
        arch_cls=None,
        tasks=[CVTask.SEG_INSTANCE, CVTask.SEG_SEMANTIC],
        annotation_format="yolo_seg",
        image_size=640,
    ),
}


def _resolve_arch_cls(name: str) -> type:
    """Resolve arch class lazily to avoid circular imports at module load."""
    if name == "student":
        from feral_segmentor.models.segmentation import StudentSegmenter

        return StudentSegmenter
    if name in ("teacher", "yolo11n-seg"):
        from feral_segmentor.models.teacher import TeacherModel

        return TeacherModel
    raise KeyError(f"no class resolver for {name!r}")


def get_profile(name: str) -> ModelProfile:
    """Return the :class:`ModelProfile` for a registered model name."""
    try:
        return _MODEL_PROFILES[name]
    except KeyError as exc:
        raise KeyError(
            f"unknown model {name!r}; registered: {sorted(_MODEL_PROFILES)}"
        ) from exc


def build_model(cfg: DictConfig) -> SegmentationModel:
    """Build a segmentation model from a model DictConfig."""
    arch = str(cfg.get("arch", DEFAULT_ARCH))
    get_profile(arch)  # raises KeyError if unknown
    arch_cls = _resolve_arch_cls(arch)
    return arch_cls.from_config(cfg)


def get_model(name: str = DEFAULT_ARCH) -> SegmentationModel:
    """Construct a model architecture by name using default arch fields."""
    get_profile(name)  # raises KeyError if unknown
    arch_cls = _resolve_arch_cls(name)
    return arch_cls()
