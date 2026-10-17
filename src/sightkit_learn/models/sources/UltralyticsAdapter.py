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

from typing import Any

from omegaconf import DictConfig
from torch import nn

from sightkit_learn.models.ModelProperties import ModelProperties
from sightkit_learn.models.sources.SourceAdapter import SourceAdapter
from sightkit_learn.tasks import CVTask
from sightkit_learn.utils import get_logger

SOURCE_KEY = "ultralytics"
log = get_logger(__name__)

_TASK_TO_OUTPUTS: dict[str, list[CVTask]] = {
    "detect": [CVTask.DETECTION],
    "segment": [CVTask.SEG_INSTANCE],
    "classify": [CVTask.CLASSIFICATION],
    "pose": [CVTask.POSE],
}


class UltralyticsAdapter(SourceAdapter):
    """Load native task models while preserving provider head and criterion selection."""

    def fetch(self, cfg: DictConfig) -> nn.Module:
        """Load a configured model and delegate class-count adjustment to Ultralytics."""
        from ultralytics import YOLO

        log.info("loading ultralytics model %s", cfg.architecture.id)
        loaded: Any = YOLO(cfg.architecture.id, **cfg.architecture.get("kwargs", {}))
        loaded_model: Any = loaded.model
        num_classes = getattr(cfg.architecture, "num_classes", None)
        if num_classes is None:
            return loaded_model
        from ultralytics.nn.tasks import ClassificationModel

        if loaded.task == "classify":
            ClassificationModel.reshape_outputs(loaded_model, num_classes)
            model = loaded_model
        elif loaded_model.model[-1].nc != num_classes:
            model_class = loaded.task_map[loaded.task]["model"]
            model = model_class(loaded_model.yaml, nc=num_classes, verbose=False)
            model.load(loaded_model, verbose=False)
        else:
            model = loaded_model
        assert isinstance(model, nn.Module), f"expected nn.Module, got {type(model)}"
        return model

    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> tuple[ModelProperties, dict]:
        from ultralytics import YOLO

        from sightkit_learn.models.register_model import load_model_registry

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
