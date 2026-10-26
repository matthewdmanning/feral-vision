"""HuggingFace Hub source adapter."""

from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from huggingface_hub import hf_hub_download, model_info
from hydra.utils import instantiate
from omegaconf import DictConfig
from torch import nn

from sightkit_learn.models.ModelProperties import ModelProperties
from sightkit_learn.models.sources.SourceAdapter import SourceAdapter
from sightkit_learn.tasks import CVTask
from sightkit_learn.utils import get_logger

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
    """Inspect Hub metadata and load the Hydra-selected Transformers task head."""

    discovery_filters = SourceAdapter.discovery_filters | {"pipeline_tag"}

    def list_models(self, *, query=None, repository=None, pipeline_tag=None):
        """Use this function to discover Hugging Face repositories without downloading model weights."""
        from huggingface_hub import HfApi

        for model in HfApi().list_models(
            search=query,
            author=repository,
            pipeline_tag=pipeline_tag,
            sort="downloads",
        ):
            yield {
                "model_id": model.id,
                "architecture_location": f"https://huggingface.co/{model.id}",
                "pipeline_tag": model.pipeline_tag,
            }

    def fetch(self, cfg: DictConfig, *, task: str | None = None) -> nn.Module:
        """Load configured weights with native options and the selected task-head class.

        Parameters
        ----------
        cfg : DictConfig
            Model source, optional weight destination, and constructor options.
        task : str, optional
            Training task selected by Hydra; omitted for legacy generic loading.

        Returns
        -------
        nn.Module
            Native PyTorch module with the selected task implementation.
        """
        options = instantiate(cfg.architecture.get("kwargs", {}), _convert_="all")
        if cfg.architecture.get("num_classes") is not None:
            options["num_labels"] = cfg.architecture.num_classes
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
            return _load_local(dest, list(weights.id), task=task, **options)

        return _load_direct(cfg.architecture.id, task=task, **options)

    def inspect(self, cfg: DictConfig) -> tuple[ModelProperties, dict]:
        try:
            info = model_info(cfg.architecture.id)
            tag = getattr(info, "pipeline_tag", None)
            model_cfg = dict(getattr(info, "config", None) or {})
            files = [item.rfilename for item in (getattr(info, "siblings", None) or [])]
            if "config.json" in files:
                config_path = hf_hub_download(
                    repo_id=cfg.architecture.id,
                    filename="config.json",
                    revision=info.sha,
                )
                model_cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
            props = ModelProperties(
                model_outputs=_TAG_TO_OUTPUTS.get(tag or "", []),
            )
            metadata = {
                "pipeline_tag": tag,
                "config": {
                    key: model_cfg[key]
                    for key in (
                        "model_type",
                        "architectures",
                        "num_labels",
                        "id2label",
                        "label2id",
                        "image_size",
                        "num_channels",
                    )
                    if key in model_cfg
                },
                "available_weights": [
                    name
                    for name in files
                    if name.endswith(
                        (".safetensors", ".bin", ".pt", ".pth", ".index.json")
                    )
                ],
            }
            return props, metadata
        except Exception as exc:
            raise RuntimeError(
                f"could not inspect {cfg.architecture.id!r} from HF Hub metadata ({exc})"
            ) from exc


def _auto_model(task: str | None):
    """Select the upstream Transformers task-head auto class without fetching a model."""
    import transformers
    from sightkit_learn.tasks import TRAINING_TASKS

    classes = {
        "generic": "AutoModel",
        "classification": "AutoModelForImageClassification",
        "detection": "AutoModelForObjectDetection",
        "semantic_segmentation": "AutoModelForSemanticSegmentation",
        "instance_segmentation": "AutoModelForInstanceSegmentation",
        "panoptic_segmentation": "AutoModelForUniversalSegmentation",
        "pose": "AutoModelForPoseEstimation",
    }
    return getattr(transformers, classes[TRAINING_TASKS[task or "generic"]])


def _load_local(
    dest: Path, filenames: list[str], *, task: str | None = None, **options: Any
) -> nn.Module:
    """Load an explicit serialized module or a local Transformers task model."""
    if len(filenames) == 1 and Path(filenames[0]).suffix in {".pt", ".pth"}:
        import torch

        return torch.load(dest / filenames[0], map_location="cpu", weights_only=False)
    return _auto_model(task).from_pretrained(
        str(dest), local_files_only=True, **options
    )


def _load_direct(repo_id: str, *, task: str | None = None, **options: Any) -> nn.Module:
    """Load the selected upstream task class using the configured provider options."""
    return _auto_model(task).from_pretrained(repo_id, **options)
