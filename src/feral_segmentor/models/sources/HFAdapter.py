"""HuggingFace Hub source adapter."""

from __future__ import annotations

from pathlib import Path

from huggingface_hub import hf_hub_download, model_info
from omegaconf import DictConfig
from torch import nn

from feral_segmentor.models.ModelProperties import ModelProperties
from feral_segmentor.models.sources.SourceAdapter import SourceAdapter, _inspect_loaded
from feral_segmentor.tasks import CVTask
from feral_segmentor.utils import get_logger

SOURCE_KEY = "hf_hub"
log = get_logger(__name__)

_TAG_TO_OUTPUTS: dict[str, list[CVTask]] = {
    "image-classification": [CVTask.CLASSIFICATION],
    "object-detection": [CVTask.DETECTION],
    "pose-estimation": [CVTask.POSE],
    "semantic-segmentation": [CVTask.SEG_SEMANTIC],
    "instance-segmentation": [CVTask.SEG_INSTANCE],
    "image-segmentation": [CVTask.SEG_SEMANTIC, CVTask.SEG_INSTANCE],
}


class HFAdapter(SourceAdapter):
    def fetch(self, cfg: DictConfig) -> nn.Module:
        weights = getattr(cfg, "weights", None)
        location = getattr(weights, "location", None) if weights else None

        if weights and location:
            dest = Path(location)
            dest.mkdir(parents=True, exist_ok=True)
            for filename in weights.id:
                if not (dest / filename).exists():
                    log.info("fetching %s from %s", filename, cfg.architecture.id)
                    hf_hub_download(
                        repo_id=cfg.architecture.id, filename=filename, local_dir=dest
                    )
            return _load_local(dest, list(weights.id))

        return _load_direct(cfg.architecture.id)

    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> tuple[ModelProperties, dict]:
        from feral_segmentor.models.register_model import load_model_registry

        try:
            return load_model_registry(cfg.architecture.id), {}
        except KeyError:
            pass

        try:
            info = model_info(cfg.architecture.id)
            tag = getattr(info, "pipeline_tag", None)
            model_cfg = getattr(info, "config", None) or {}
            props = ModelProperties(
                n_classes=model_cfg.get("num_labels") or model_cfg.get("num_classes"),
                model_outputs=_TAG_TO_OUTPUTS.get(tag or "", []),
            )
            metadata = {
                "pipeline_tag": tag,
                "tags": list(getattr(info, "tags", []) or []),
                "config": dict(model_cfg),
            }
            return props, metadata
        except Exception as exc:
            if not fetch_if_needed:
                raise RuntimeError(
                    f"could not inspect {cfg.architecture.id!r} from HF Hub metadata "
                    f"({exc}); pass fetch_if_needed=True to fetch and inspect locally"
                ) from exc

        return _inspect_loaded(self.fetch(cfg))


def _load_local(dest: Path, filenames: list[str]) -> nn.Module:
    import torch

    try:
        from transformers import AutoModel

        return AutoModel.from_pretrained(str(dest), local_files_only=True)
    except Exception:
        pass
    return torch.load(dest / filenames[0], map_location="cpu", weights_only=False)


def _load_direct(repo_id: str) -> nn.Module:
    try:
        from transformers import AutoModel

        return AutoModel.from_pretrained(repo_id)
    except Exception:
        pass
    raise RuntimeError(
        f"cannot load {repo_id!r} directly into memory; provide cfg.weights.location"
    )
