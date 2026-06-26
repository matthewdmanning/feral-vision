"""Segmentation training losses.

Combines soft Dice and cross-entropy over class logits, with optional
knowledge-distillation (KL against a teacher's soft targets). All numeric
defaults come from :mod:`feral_segmentor.constants`; nothing is inlined.

Logit tensors follow the ``SegmentationOutput`` contract: shape
``(B, num_classes, H, W)``. Targets are long masks ``(B, H, W)`` of class
indices (one-hot ``(B, C, H, W)`` is also accepted by :func:`dice_loss`).
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F

from feral_segmentor.constants import DICE_SMOOTH


def _to_class_indices(target: torch.Tensor, num_classes: int) -> torch.Tensor:
    """Return a long index mask ``(B, H, W)`` from an index or one-hot target."""
    if target.dim() == 4 and target.shape[1] == num_classes:
        # One-hot / channel-first probabilities -> hard class indices.
        return target.argmax(dim=1)
    return target.long()


def dice_loss(
    pred: torch.Tensor,
    target: torch.Tensor,
    smooth: float = DICE_SMOOTH,
) -> torch.Tensor:
    """Soft (multi-class) Dice loss.

    Args:
        pred: Class logits ``(B, C, H, W)``.
        target: Long class-index mask ``(B, H, W)`` or one-hot ``(B, C, H, W)``.
        smooth: Laplace smoothing added to numerator and denominator.

    Returns:
        Scalar ``1 - mean_dice`` averaged over classes and batch.
    """
    num_classes = pred.shape[1]
    probs = F.softmax(pred, dim=1)

    indices = _to_class_indices(target, num_classes)
    target_onehot = F.one_hot(indices, num_classes=num_classes)
    # (B, H, W, C) -> (B, C, H, W) to align with probs.
    target_onehot = target_onehot.permute(0, 3, 1, 2).to(probs.dtype)

    # Reduce over spatial dims, keeping batch and class.
    dims = (2, 3)
    intersection = (probs * target_onehot).sum(dim=dims)
    cardinality = probs.sum(dim=dims) + target_onehot.sum(dim=dims)

    dice = (2.0 * intersection + smooth) / (cardinality + smooth)
    return 1.0 - dice.mean()


def _distillation_loss(
    logits: torch.Tensor,
    teacher_logits: torch.Tensor,
    temperature: float,
) -> torch.Tensor:
    """Standard KD KL term: KL(softmax(teacher/T) || softmax(student/T)) * T^2."""
    student_log_probs = F.log_softmax(logits / temperature, dim=1)
    teacher_probs = F.softmax(teacher_logits / temperature, dim=1)
    kl = F.kl_div(student_log_probs, teacher_probs, reduction="batchmean")
    return kl * (temperature * temperature)


def segmentation_loss(
    logits: torch.Tensor,
    target: torch.Tensor,
    cfg: Any,
    teacher_logits: torch.Tensor | None = None,
) -> torch.Tensor:
    """Weighted Dice + cross-entropy, with optional distillation.

    Args:
        logits: Student class logits ``(B, C, H, W)``.
        target: Long class-index mask ``(B, H, W)``.
        cfg: ``TrainConfig``/``DictConfig`` with ``dice_weight``, ``bce_weight``,
            ``distill_weight`` and ``distill_temperature``.
        teacher_logits: Teacher logits ``(B, C, H, W)``; only required when
            ``cfg.distill_weight > 0``.

    Returns:
        Scalar combined loss.
    """
    num_classes = logits.shape[1]
    indices = _to_class_indices(target, num_classes)

    dice = dice_loss(logits, indices)
    ce = F.cross_entropy(logits, indices)
    loss = cfg.dice_weight * dice + cfg.bce_weight * ce

    if cfg.distill_weight > 0:
        if teacher_logits is None:
            raise ValueError("teacher_logits is required when cfg.distill_weight > 0")
        distill = _distillation_loss(logits, teacher_logits, cfg.distill_temperature)
        loss = loss + cfg.distill_weight * distill

    return loss
