"""HuggingFace Hub source adapter."""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download, model_info
from omegaconf import DictConfig
from torch import nn

from feral_segmentor.models.ModelProperties import ModelProperties
from feral_segmentor.models.source import register_source
from feral_segmentor.tasks import CVTask
from feral_segmentor.utils import get_logger

log = get_logger(__name__)

# Maps HF pipeline_tag values to CVTask lists.
_PIPELINE_TAG_TASKS: dict[str, list[CVTask]] = {
    "image-classification": [CVTask.CLASSIFICATION],
    "object-detection": [CVTask.DETECTION],
    "pose-estimation": [CVTask.POSE],
    "semantic-segmentation": [CVTask.SEG_SEMANTIC],
    "instance-segmentation": [CVTask.SEG_INSTANCE],
    "image-segmentation": [CVTask.SEG_SEMANTIC, CVTask.SEG_INSTANCE],
}


def _tasks_from_info(info) -> list[CVTask]:
    tag = getattr(info, "pipeline_tag", None)
    return _PIPELINE_TAG_TASKS.get(tag or "", [])


def _n_classes_from_info(info) -> int | None:
    cfg = getattr(info, "config", None) or {}
    return cfg.get("num_labels") or cfg.get("num_classes")


@register_source("hf_hub")
class HFHubSource:
    def fetch(self, cfg: DictConfig) -> None:
        """Download cfg.weights.id files to cfg.weights.location. No-op per file if already present."""
        dest = Path(cfg.weights.location)
        dest.mkdir(parents=True, exist_ok=True)
        for filename in cfg.weights.id:
            if (dest / filename).exists():
                log.debug("already cached: %s", dest / filename)
                continue
            log.info("fetching %s from %s", filename, cfg.architecture.id)
            hf_hub_download(
                repo_id=cfg.architecture.id, filename=filename, local_dir=dest
            )

    def instantiate(self, cfg: DictConfig) -> nn.Module:
        """Load model from local weights. Requires fetch() to have run first."""
        import torch

        dest = Path(cfg.weights.location)
        paths = []
        for filename in cfg.weights.id:
            p = dest / filename
            if not p.exists():
                raise FileNotFoundError(
                    f"weight file not found: {p} — run fetch() first"
                )
            paths.append(p)

        try:
            from transformers import AutoModel

            return AutoModel.from_pretrained(str(dest), local_files_only=True)
        except Exception:
            pass

        # Generic fallback: load the first weight file as a full model.
        return torch.load(paths[0], map_location="cpu", weights_only=False)

    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> ModelProperties:
        """Return model properties. Tries hub metadata first; fetches and loads if needed."""
        try:
            info = model_info(cfg.architecture.id)
            return ModelProperties(
                n_classes=_n_classes_from_info(info),
                model_outputs=_tasks_from_info(info),
            )
        except Exception as exc:
            if not fetch_if_needed:
                raise RuntimeError(
                    f"could not inspect {cfg.architecture.id!r} from hub metadata "
                    f"({exc}); pass fetch_if_needed=True to fetch and inspect locally"
                ) from exc

        self.fetch(cfg)
        model = self.instantiate(cfg)
        return _inspect_torch_model(model)


def _inspect_torch_model(model: nn.Module) -> ModelProperties:
    """Infer n_classes and cv_tasks from a loaded nn.Module via output shape."""

    n_classes = None
    for name, mod in reversed(list(model.named_modules())):
        if isinstance(mod, nn.Linear):
            n_classes = mod.out_features
            break
        if isinstance(mod, nn.Conv2d):
            n_classes = mod.out_channels
            break

    return ModelProperties(n_classes=n_classes, model_outputs=[])
