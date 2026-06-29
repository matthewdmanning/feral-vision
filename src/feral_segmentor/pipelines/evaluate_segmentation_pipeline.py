"""Evaluate a segmentation checkpoint and write metrics.json (Hydra entrypoint)."""

from __future__ import annotations

import os
from pathlib import Path

import hydra
import torch
from omegaconf import DictConfig

from feral_segmentor import constants as C
from feral_segmentor.config.store import register_configs
from feral_segmentor.io_utils import write_json
from feral_segmentor.training.metrics import dice_score, mean_iou
from feral_segmentor.utils import get_logger

register_configs()

log = get_logger(__name__)

_DEFAULT_METRIC_VALUE: float = 0.0
_METRICS_FILENAME = "metrics.json"


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    """Load a checkpoint and write mean_iou and dice_score to metrics.json."""
    register_configs()

    try:
        orig_cwd = Path(hydra.utils.get_original_cwd())
    except ValueError:
        orig_cwd = Path(os.getcwd())

    ckpt_path = orig_cwd / "models" / "registry" / "best.pt"
    metrics_path = orig_cwd / _METRICS_FILENAME

    metrics: dict[str, float] = {
        "mean_iou": _DEFAULT_METRIC_VALUE,
        "dice_score": _DEFAULT_METRIC_VALUE,
    }

    if not ckpt_path.exists():
        log.warning("checkpoint %s not found; writing default metrics", ckpt_path)
        write_json(metrics, metrics_path)
        return

    try:
        payload = torch.load(ckpt_path, map_location=C.DEFAULT_DEVICE)
    except Exception as exc:  # noqa: BLE001 - robustness for the DVC stage
        log.warning("failed to load %s (%s); writing default metrics", ckpt_path, exc)
        write_json(metrics, metrics_path)
        return

    preds = payload.get("preds") if isinstance(payload, dict) else None
    targets = payload.get("targets") if isinstance(payload, dict) else None

    if preds is None or targets is None:
        log.warning(
            "checkpoint lacks 'preds'/'targets'; cannot evaluate, writing defaults"
        )
        write_json(metrics, metrics_path)
        return

    preds = torch.as_tensor(preds)
    targets = torch.as_tensor(targets)
    metrics["mean_iou"] = mean_iou(preds, targets)
    metrics["dice_score"] = dice_score(preds, targets)
    log.info("metrics: %s", metrics)
    write_json(metrics, metrics_path)


if __name__ == "__main__":
    main()
