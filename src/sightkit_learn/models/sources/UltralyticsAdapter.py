"""Ultralytics source adapter.

architecture.id  â€” model filename (e.g. 'yolo11n-seg.pt', 'yolo11n.pt')
weights          â€” not used; ultralytics bundles weights with the model file

Task strings returned by model.task and their CVTask mapping:
  detect   â†’ CVTask.DETECTION
  segment  â†’ CVTask.SEG_INSTANCE
  classify â†’ CVTask.CLASSIFICATION
  pose     â†’ CVTask.POSE
"""

from __future__ import annotations

from typing import Any
from pathlib import Path

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
    "semantic": [CVTask.SEG_SEMANTIC],
}


def _model_class(model_id: str) -> str:
    """Use this function to select the native Ultralytics constructor for a catalogue entry."""
    name = Path(model_id).name.casefold()
    if name.startswith("fastsam"):
        return "FastSAM"
    if name.startswith(("sam", "mobile_sam")):
        return "SAM"
    if name.startswith("yolo_nas"):
        return "NAS"
    if name.startswith("rtdetr"):
        return "RTDETR"
    return "YOLO"


class UltralyticsAdapter(SourceAdapter):
    """Load native task models while preserving provider head and criterion selection."""

    discovery_filters = SourceAdapter.discovery_filters | {"kind"}

    def list_models(self, *, query=None, repository=None, pipeline_tag=None):
        """Use this function to enumerate installed Ultralytics architectures and known pretrained checkpoints."""
        from ultralytics.utils import ROOT
        from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES

        if repository or pipeline_tag:
            raise ValueError(
                "ultralytics discovery uses its installed catalogue; use query to filter model names"
            )
        identifiers = {name for name in GITHUB_ASSETS_NAMES if name.endswith(".pt")}
        identifiers.update(
            path.relative_to(ROOT).as_posix()
            for path in (ROOT / "cfg/models").rglob("*.yaml")
        )
        for model_id in sorted(identifiers):
            if not query or query.casefold() in model_id.casefold():
                yield {
                    "model_id": model_id,
                    "architecture_location": f"ultralytics.{_model_class(model_id)}",
                    "kind": "checkpoint"
                    if model_id.endswith(".pt")
                    else "architecture",
                }

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

    def inspect(self, cfg: DictConfig) -> tuple[ModelProperties, dict]:
        import inspect
        import re
        import ultralytics
        from ultralytics.nn.tasks import guess_model_task
        from ultralytics.utils import ROOT, YAML
        from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES

        model_id = str(cfg.architecture.id)
        location = cfg.architecture.get("location")
        class_name = (
            location.removeprefix("ultralytics.")
            if location
            else _model_class(model_id)
        )
        if class_name not in {
            "YOLO",
            "YOLOWorld",
            "YOLOE",
            "SAM",
            "FastSAM",
            "NAS",
            "RTDETR",
        }:
            raise ValueError(f"unsupported Ultralytics constructor {location!r}")
        path = Path(model_id)
        stem = path.stem
        canonical = re.sub(r"(\d+)[nslmx](?=$|-)", r"\1", stem)
        candidates = [
            candidate
            for candidate in (ROOT / "cfg/models").rglob("*.yaml")
            if candidate.stem in {stem, canonical}
        ]
        if path.suffix in {".yaml", ".yml"} and path.is_file():
            architecture_path = path
        elif path.suffix in {".yaml", ".yml"} and (ROOT / path).is_file():
            architecture_path = ROOT / path
        elif len(candidates) == 1:
            architecture_path = candidates[0]
        else:
            architecture_path = None
        if architecture_path is None and path.name not in GITHUB_ASSETS_NAMES:
            raise ValueError(
                f"no published architecture metadata for {model_id!r}; supply an architecture YAML identifier"
            )
        architecture = YAML.load(architecture_path) if architecture_path else {}
        task = guess_model_task(architecture) if architecture.get("head") else None
        if task is None:
            task = {
                "SAM": "segment",
                "FastSAM": "segment",
                "NAS": "detect",
                "RTDETR": "detect",
            }.get(class_name)
        checkpoints = {stem + ".pt"}
        if path.suffix in {".yaml", ".yml"}:
            base, separator, suffix = stem.partition("-")
            checkpoints.update(
                f"{base}{scale}{separator}{suffix}.pt"
                for scale in architecture.get("scales", {})
            )
        metadata = {
            "task": task,
            "nc": architecture.get("nc"),
            "names": None,
            "architecture_file": str(architecture_path) if architecture_path else None,
            "architecture_location": f"ultralytics.{class_name}",
            "documentation": inspect.getdoc(getattr(ultralytics, class_name).__init__),
            "available_weights": sorted(checkpoints & GITHUB_ASSETS_NAMES),
        }
        return ModelProperties(
            model_outputs=_TASK_TO_OUTPUTS.get(task or "", [])
        ), metadata
