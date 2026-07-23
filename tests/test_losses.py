"""Verify segmentation losses preserve Dice and configured weighting contracts."""

from __future__ import annotations

# third-party
import pytest
import torch
import torch.nn.functional as F
from omegaconf import DictConfig, OmegaConf

# project
from feral_vision.training.losses import dice_loss, segmentation_loss


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _loss_cfg(**overrides: float) -> DictConfig:
    """Build the loss settings consumed by ``segmentation_loss``."""
    defaults = {
        "dice_weight": 1.0,
        "bce_weight": 1.0,
        "distill_weight": 0.0,
        "distill_temperature": 1.0,
    }
    return OmegaConf.create({**defaults, **overrides})


@pytest.fixture(params=["class-indices", "one-hot"])
def segmentation_batch(
    request: pytest.FixtureRequest,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Provide deterministic 2D logits and equivalent target encodings."""
    target_indices = torch.tensor([[[0, 1], [1, 0]]], dtype=torch.long)
    logits = torch.tensor(
        [[[[8.0, -8.0], [-8.0, 8.0]], [[-8.0, 8.0], [8.0, -8.0]]]],
        requires_grad=True,
    )
    if request.param == "one-hot":
        target = F.one_hot(target_indices, num_classes=2).permute(0, 3, 1, 2).float()
    else:
        target = target_indices
    return logits, target


# ---------------------------------------------------------------------------
# Dice behavior
# ---------------------------------------------------------------------------


def test_dice_loss_distinguishes_perfect_and_incorrect_predictions(
    segmentation_batch: tuple[torch.Tensor, torch.Tensor],
) -> None:
    logits, target = segmentation_batch

    perfect_loss = dice_loss(logits, target)
    incorrect_loss = dice_loss(-logits, target)

    assert perfect_loss.detach() < 1e-6
    assert incorrect_loss > perfect_loss + 0.5


# ---------------------------------------------------------------------------
# Combined segmentation loss
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dice_weight", "bce_weight"),
    [(1.0, 0.0), (0.0, 1.0), (0.25, 0.75)],
)
def test_segmentation_loss_applies_configured_component_weights(
    segmentation_batch: tuple[torch.Tensor, torch.Tensor],
    dice_weight: float,
    bce_weight: float,
) -> None:
    logits, target = segmentation_batch
    cfg = _loss_cfg(dice_weight=dice_weight, bce_weight=bce_weight)
    target_indices = target.argmax(dim=1) if target.dim() == 4 else target

    loss = segmentation_loss(logits, target, cfg)
    expected = dice_weight * dice_loss(
        logits, target_indices
    ) + bce_weight * F.cross_entropy(logits, target_indices)

    assert loss.shape == torch.Size([])
    assert torch.allclose(loss, expected)
    loss.backward()
    assert logits.grad is not None
    assert torch.isfinite(logits.grad).all()
