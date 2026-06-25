from __future__ import annotations

from pathlib import Path

import torch
from omegaconf import DictConfig

from feral_segmentor.data.fetch import fetch_data
from feral_segmentor.data.transforms import preprocess
from feral_segmentor.io_utils import load_image
from feral_segmentor.models.base import SegmentationModel, SegmentationOutput
from feral_segmentor.models.registry import build_model
from feral_segmentor.models.source import build_model_source
from feral_segmentor.utils import get_logger

logger = get_logger(__name__)


def _resolve_source(cfg: DictConfig) -> str:
    """Pick the data source to fetch: explicit data root, else its source spec."""
    data_cfg = cfg.data
    root = getattr(data_cfg, "root", None)
    return root if root else data_cfg.source


def _maybe_load_weights(model: SegmentationModel, cfg: DictConfig) -> None:
    """Acquire weights for ``model`` and load a checkpoint if one is produced."""
    source = build_model_source(cfg.model)
    checkpoint = source.acquire(cfg.model)
    if checkpoint is None:
        logger.info("no checkpoint available for model '%s'; using initial weights", cfg.model.name)
        return
    checkpoint_path = Path(checkpoint)
    if not checkpoint_path.exists():
        logger.info("checkpoint path '%s' does not exist; using initial weights", checkpoint_path)
        return
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    load_state_dict = getattr(model, "load_state_dict", None)
    if load_state_dict is None:
        logger.warning("model '%s' does not support load_state_dict; skipping", cfg.model.name)
        return
    load_state_dict(state_dict)
    logger.info("loaded weights from '%s'", checkpoint_path)


def segment(cfg: DictConfig) -> SegmentationOutput:
    """Run the full config-driven segmentation pipeline for a single image.

    Steps: fetch data -> load image -> preprocess -> build model -> acquire
    weights (if a checkpoint exists) -> predict.
    """
    source = _resolve_source(cfg)
    path = fetch_data(source)
    image = load_image(path)
    image_tensor = preprocess(image)

    model = build_model(cfg.model)
    _maybe_load_weights(model, cfg)

    return model.predict(image_tensor)
