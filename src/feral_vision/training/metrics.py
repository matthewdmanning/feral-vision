"""Semantic-segmentation metrics (IoU / Dice) and the DVC ``evaluate`` entrypoint.

Both metrics accept either predicted class indices ``(B, H, W)`` or raw logits
``(B, C, H, W)`` (reduced via ``argmax`` over the channel dim). Targets are long
tensors of class indices ``(B, H, W)``. Scores are averaged over the classes that
appear in either prediction or target, so empty classes never dilute the mean.
"""

from __future__ import annotations

import os
from pathlib import Path

import hydra
import torch
from omegaconf import DictConfig

from feral_vision.config.store import register_configs
from feral_vision.io_utils import write_json
from feral_vision.utils import get_logger

logger = get_logger(__name__)

register_configs()

# Logits carry a class dimension, so a 4-D input is (B, C, H, W).
_LOGITS_NDIM = 4
# Metric value written when evaluation inputs are unavailable.
_DEFAULT_METRIC_VALUE: float = 0.0
# Output filename for the DVC ``evaluate`` stage (see dvc.yaml).
_METRICS_FILENAME = "metrics.json"


def _to_class_indices(pred: torch.Tensor) -> torch.Tensor:
    """Reduce logits ``(B, C, H, W)`` to class indices; pass indices through."""
    if pred.ndim == _LOGITS_NDIM:
        return pred.argmax(dim=1)
    return pred


def _infer_num_classes(
    pred: torch.Tensor, target: torch.Tensor, num_classes: int | None
) -> int:
    if num_classes is not None:
        return num_classes
    return int(max(pred.max().item(), target.max().item())) + 1


def _per_class_scores(
    pred: torch.Tensor,
    target: torch.Tensor,
    num_classes: int | None,
    *,
    dice: bool,
) -> float:
    """Mean per-class IoU or Dice over classes present in pred or target."""
    pred = _to_class_indices(pred)
    if pred.shape != target.shape:
        raise ValueError(
            f"pred shape {tuple(pred.shape)} != target shape {tuple(target.shape)}"
        )
    n = _infer_num_classes(pred, target, num_classes)

    scores: list[float] = []
    for cls in range(n):
        pred_c = pred == cls
        target_c = target == cls
        intersection = float((pred_c & target_c).sum().item())
        pred_sum = float(pred_c.sum().item())
        target_sum = float(target_c.sum().item())

        if pred_sum == 0.0 and target_sum == 0.0:
            # Class absent everywhere: exclude from the mean.
            continue

        if dice:
            score = (2.0 * intersection) / (pred_sum + target_sum)
        else:
            union = pred_sum + target_sum - intersection
            score = intersection / union
        scores.append(score)

    if not scores:
        return 1.0  # nothing to compare against -> trivially perfect
    return sum(scores) / len(scores)


def mean_iou(
    pred: torch.Tensor, target: torch.Tensor, num_classes: int | None = None
) -> float:
    """Mean Intersection-over-Union over classes present in pred or target.

    Args:
        pred: Predicted class indices ``(B, H, W)`` or logits ``(B, C, H, W)``.
        target: Ground-truth class indices ``(B, H, W)`` (long).
        num_classes: Number of classes; inferred from the data when ``None``.
    """
    return _per_class_scores(pred, target, num_classes, dice=False)


def dice_score(
    pred: torch.Tensor, target: torch.Tensor, num_classes: int | None = None
) -> float:
    """Mean per-class Dice (F1) over classes present in pred or target.

    Args:
        pred: Predicted class indices ``(B, H, W)`` or logits ``(B, C, H, W)``.
        target: Ground-truth class indices ``(B, H, W)`` (long).
        num_classes: Number of classes; inferred from the data when ``None``.
    """
    return _per_class_scores(pred, target, num_classes, dice=True)


@hydra.main(version_base=None, config_path="../../../conf", config_name="runs/baseline")
def main(cfg: DictConfig) -> None:
    register_configs()

    # Hydra changes the working directory; resolve paths relative to the
    # original cwd so the DVC dep/output paths match.
    try:
        orig_cwd = Path(hydra.utils.get_original_cwd())
    except ValueError:
        orig_cwd = Path(os.getcwd())

    ckpt_path = orig_cwd / "models" / "registry" / "best.pt"
    metrics_path = orig_cwd / _METRICS_FILENAME

    metrics = {"mean_iou": _DEFAULT_METRIC_VALUE, "dice_score": _DEFAULT_METRIC_VALUE}

    if not ckpt_path.exists():
        logger.warning("checkpoint %s not found; writing default metrics", ckpt_path)
        write_json(metrics, metrics_path)
        return

    try:
        payload = torch.load(ckpt_path, map_location="cpu")
    except Exception as exc:  # noqa: BLE001 - robustness for the DVC stage
        logger.warning(
            "failed to load %s (%s); writing default metrics", ckpt_path, exc
        )
        write_json(metrics, metrics_path)
        return

    preds = payload.get("preds") if isinstance(payload, dict) else None
    targets = payload.get("targets") if isinstance(payload, dict) else None

    if preds is None or targets is None:
        logger.warning(
            "checkpoint lacks 'preds'/'targets'; cannot evaluate, writing defaults"
        )
        write_json(metrics, metrics_path)
        return

    preds = torch.as_tensor(preds)
    targets = torch.as_tensor(targets)
    metrics["mean_iou"] = mean_iou(preds, targets)
    metrics["dice_score"] = dice_score(preds, targets)
    logger.info("metrics: %s", metrics)
    write_json(metrics, metrics_path)


if __name__ == "__main__":
    main()
