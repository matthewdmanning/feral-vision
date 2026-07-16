"""Ultralytics source adapter.

architecture.id  — model filename (e.g. 'yolo11n-seg.pt', 'yolo11n.pt')
weights          — not used; ultralytics bundles weights with the model file

Task strings returned by model.task and their CVTask mapping:
  detect   → CVTask.DETECTION
  segment  → CVTask.SEG_INSTANCE
  classify → CVTask.CLASSIFICATION
  pose     → CVTask.POSE
"""

from __future__ import annotations

from omegaconf import DictConfig
from torch import nn

from feral_vision.models.ModelProperties import ModelProperties
from feral_vision.models.sources.SourceAdapter import SourceAdapter
from feral_vision.tasks import CVTask
from feral_vision.utils import get_logger

SOURCE_KEY = "ultralytics"
log = get_logger(__name__)

_TASK_TO_OUTPUTS: dict[str, list[CVTask]] = {
    "detect": [CVTask.DETECTION],
    "segment": [CVTask.SEG_INSTANCE],
    "classify": [CVTask.CLASSIFICATION],
    "pose": [CVTask.POSE],
}


class UltralyticsAdapter(SourceAdapter):
    def fetch(self, cfg: DictConfig) -> nn.Module:
        from ultralytics import YOLO

        log.info("loading ultralytics model %s", cfg.architecture.id)
        model = YOLO(cfg.architecture.id).model
        assert isinstance(model, nn.Module), f"expected nn.Module, got {type(model)}"
        return model

    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> tuple[ModelProperties, dict]:
        from ultralytics import YOLO

        from feral_vision.models.register_model import load_model_registry

        try:
            props = load_model_registry(cfg.architecture.id)
            return props, {}
        except KeyError:
            pass

        log.info("inspecting ultralytics model %s", cfg.architecture.id)
        model = YOLO(cfg.architecture.id)

        task = getattr(model, "task", None)
        names = dict(getattr(model, "names", {}))
        nc = getattr(model.model, "nc", None)

        props = ModelProperties(
            model_outputs=_TASK_TO_OUTPUTS.get(task or "", []),
        )
        metadata = {
            "task": task,
            "nc": nc,
            "names": names,
        }
        return props, metadata
