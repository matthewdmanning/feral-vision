import torch
from omegaconf import OmegaConf

from feral_segmentor import constants as C
from feral_segmentor.training.losses import dice_loss, segmentation_loss


def _make_cfg(**overrides):
    defaults = {
        "dice_weight": C.DEFAULT_DICE_WEIGHT,
        "bce_weight": C.DEFAULT_BCE_WEIGHT,
        "distill_weight": C.DEFAULT_DISTILL_WEIGHT,
        "distill_temperature": C.DEFAULT_DISTILL_TEMPERATURE,
    }
    return OmegaConf.create({**defaults, **overrides})


def test_dice_loss_near_zero_for_perfect_prediction():
    # All-background target; logits strongly favor class 0.
    target = torch.zeros(2, 4, 4, dtype=torch.long)
    pred = torch.zeros(2, 2, 4, 4)
    pred[:, 0] = 10.0
    loss = dice_loss(pred, target)
    assert float(loss) < 1e-2


def test_dice_loss_positive_for_wrong_prediction():
    target = torch.zeros(2, 4, 4, dtype=torch.long)
    pred = torch.zeros(2, 2, 4, 4)
    pred[:, 1] = 10.0  # predicts the wrong class everywhere
    loss = dice_loss(pred, target)
    assert float(loss) > 0.5


def test_dice_loss_accepts_one_hot_target():
    indices = torch.zeros(1, 4, 4, dtype=torch.long)
    onehot = torch.nn.functional.one_hot(indices, num_classes=2)
    onehot = onehot.permute(0, 3, 1, 2).float()
    pred = torch.zeros(1, 2, 4, 4)
    pred[:, 0] = 10.0
    assert float(dice_loss(pred, onehot)) < 1e-2


def test_segmentation_loss_finite_scalar():
    cfg = _make_cfg(distill_weight=0.0)
    logits = torch.randn(2, 2, 4, 4)
    target = torch.randint(0, 2, (2, 4, 4))
    loss = segmentation_loss(logits, target, cfg)
    assert loss.dim() == 0
    assert torch.isfinite(loss)


def test_segmentation_loss_ignores_teacher_when_distill_zero():
    cfg = _make_cfg(distill_weight=0.0)
    logits = torch.randn(2, 2, 4, 4)
    target = torch.randint(0, 2, (2, 4, 4))
    # Passing None must work when distillation is disabled.
    loss = segmentation_loss(logits, target, cfg, teacher_logits=None)
    assert torch.isfinite(loss)


def test_segmentation_loss_distill_adds_positive_term():
    base_cfg = _make_cfg(distill_weight=0.0)
    distill_cfg = _make_cfg(distill_weight=1.0, distill_temperature=2.0)

    torch.manual_seed(0)
    logits = torch.randn(2, 2, 4, 4)
    teacher = torch.randn(2, 2, 4, 4)
    target = torch.randint(0, 2, (2, 4, 4))

    base = segmentation_loss(logits, target, base_cfg)
    with_distill = segmentation_loss(
        logits, target, distill_cfg, teacher_logits=teacher
    )
    assert float(with_distill) > float(base)
