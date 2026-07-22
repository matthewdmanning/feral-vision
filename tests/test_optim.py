"""Tests for optimizer/scheduler/loss-fn builders.

Verify that build_optimizer / build_scheduler / build_loss_fn correctly delegate
to hydra.utils.instantiate for each supported config variant in schema.py.
"""

import pytest
import torch
import torch.nn as nn
from omegaconf import OmegaConf

from feral_vision.config.schema import (
    AdamConfig,
    AdamWConfig,
    BCEWithLogitsConfig,
    CosineAnnealingConfig,
    CrossEntropyConfig,
    SGDConfig,
    StepLRConfig,
)
from feral_vision.training.optim import (
    build_loss_fn,
    build_optimizer,
    build_scheduler,
)


@pytest.fixture
def module() -> nn.Module:
    """Small 2D image model supplying parameters to optimizer builders."""
    return nn.Conv2d(3, 2, kernel_size=1)


# --- build_optimizer ---------------------------------------------------------


def test_build_optimizer_adamw(module):
    cfg = OmegaConf.structured(AdamWConfig(lr=1e-3))
    opt = build_optimizer(module.parameters(), cfg)
    assert isinstance(opt, torch.optim.AdamW)
    assert opt.param_groups[0]["lr"] == pytest.approx(1e-3)


def test_build_optimizer_adam(module):
    cfg = OmegaConf.structured(AdamConfig(lr=5e-4))
    opt = build_optimizer(module.parameters(), cfg)
    assert isinstance(opt, torch.optim.Adam)
    assert opt.param_groups[0]["lr"] == pytest.approx(5e-4)


def test_build_optimizer_sgd_has_momentum(module):
    cfg = OmegaConf.structured(SGDConfig(lr=1e-2, momentum=0.9))
    opt = build_optimizer(module.parameters(), cfg)
    assert isinstance(opt, torch.optim.SGD)
    assert opt.param_groups[0]["lr"] == pytest.approx(1e-2)
    assert opt.param_groups[0]["momentum"] == pytest.approx(0.9)


# --- build_scheduler ---------------------------------------------------------


def test_build_scheduler_none_returns_none(module):
    opt = build_optimizer(module.parameters(), OmegaConf.structured(AdamWConfig()))
    assert build_scheduler(opt, None) is None


def test_build_scheduler_step(module):
    opt = build_optimizer(module.parameters(), OmegaConf.structured(AdamWConfig()))
    sched_cfg = OmegaConf.structured(StepLRConfig(step_size=5, gamma=0.5))
    sched = build_scheduler(opt, sched_cfg)
    assert isinstance(sched, torch.optim.lr_scheduler.StepLR)
    assert sched.step_size == 5
    assert sched.gamma == pytest.approx(0.5)


def test_build_scheduler_cosine(module):
    opt = build_optimizer(module.parameters(), OmegaConf.structured(AdamWConfig()))
    sched_cfg = OmegaConf.structured(CosineAnnealingConfig(T_max=10))
    sched = build_scheduler(opt, sched_cfg)
    assert isinstance(sched, torch.optim.lr_scheduler.CosineAnnealingLR)
    assert sched.T_max == 10


# --- build_loss_fn -----------------------------------------------------------


def test_build_loss_fn_cross_entropy():
    loss_fn = build_loss_fn(OmegaConf.structured(CrossEntropyConfig()))
    assert isinstance(loss_fn, torch.nn.CrossEntropyLoss)


def test_build_loss_fn_bce_with_logits():
    loss_fn = build_loss_fn(OmegaConf.structured(BCEWithLogitsConfig()))
    assert isinstance(loss_fn, torch.nn.BCEWithLogitsLoss)


def test_build_loss_fn_cross_entropy_label_smoothing():
    loss_fn = build_loss_fn(
        OmegaConf.structured(CrossEntropyConfig(label_smoothing=0.1))
    )
    assert isinstance(loss_fn, torch.nn.CrossEntropyLoss)
    assert loss_fn.label_smoothing == pytest.approx(0.1)
