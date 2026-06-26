"""Semantic-segmentation metrics: mean IoU and Dice score.

Both metrics accept either predicted class indices ``(B, H, W)`` or raw logits
``(B, C, H, W)`` (reduced via ``argmax`` over the channel dim). Targets are long
tensors of class indices ``(B, H, W)``. Scores are averaged over the classes that
appear in either prediction or target, so empty classes never dilute the mean.
"""

from __future__ import annotations

import torch

# Logits carry a class dimension, so a 4-D input is (B, C, H, W).
_LOGITS_NDIM = 4


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
