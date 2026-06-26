"""HuggingFace Hub weight-source adapter."""

from __future__ import annotations

from pathlib import Path

import torch
from huggingface_hub import hf_hub_download
from omegaconf import DictConfig
from torch import nn

from feral_segmentor.models.registry import build_model
from feral_segmentor.models.source import register_source
from feral_segmentor.utils import get_logger

log = get_logger(__name__)


@register_source("hub")
class HubSource:
    """Download weights from the HuggingFace Hub and load into a model."""

    def load(self, cfg: DictConfig) -> nn.Module:
        """Fetch files listed in cfg from the Hub, build a model, load weights."""
        weights_dir = Path(cfg.weights_dir)
        weights_dir.mkdir(parents=True, exist_ok=True)
        paths = []
        for filename in cfg.files:
            log.info("Fetching %s from %s", filename, cfg.repo_id)
            downloaded = hf_hub_download(
                repo_id=cfg.repo_id, filename=filename, local_dir=weights_dir
            )
            paths.append(Path(downloaded))
        model = build_model(cfg)
        if paths:
            state_dict = torch.load(paths[0], map_location="cpu")
            model.load_state_dict(state_dict, strict=False)
        return model
