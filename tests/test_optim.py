"""Tests for optimizer/scheduler builders (unit D).

Self-contained: builds a 1-parameter dummy module and structured ``TrainConfig``
nodes directly, with no dependency on other pipeline units.
"""

import pytest
import torch
import torch.nn as nn
from omegaconf import OmegaConf

from feral_segmentor.config.schema import TrainConfig
from feral_segmentor.training.optim import build_optimizer, build_scheduler


@pytest.fixture
def module() -> nn.Module:
    return nn.Linear(1, 1)


def test_build_optimizer_adam(module):
    cfg = OmegaConf.structured(TrainConfig(optimizer="adam"))
    opt = build_optimizer(module.parameters(), cfg)
    assert isinstance(opt, torch.optim.Adam)
    group = opt.param_groups[0]
    assert group["lr"] == cfg.lr
    assert group["weight_decay"] == cfg.weight_decay


def test_build_optimizer_sgd_has_momentum(module):
    cfg = OmegaConf.structured(TrainConfig(optimizer="sgd"))
    opt = build_optimizer(module.parameters(), cfg)
    assert isinstance(opt, torch.optim.SGD)
    group = opt.param_groups[0]
    assert group["lr"] == cfg.lr
    assert group["weight_decay"] == cfg.weight_decay
    assert group["momentum"] == cfg.momentum


def test_build_optimizer_unknown_raises(module):
    cfg = OmegaConf.structured(TrainConfig(optimizer="rmsprop"))
    with pytest.raises(ValueError, match="unknown optimizer"):
        build_optimizer(module.parameters(), cfg)


def test_build_scheduler_none_returns_none(module):
    cfg = OmegaConf.structured(TrainConfig(scheduler="none"))
    opt = build_optimizer(module.parameters(), cfg)
    assert build_scheduler(opt, cfg) is None


def test_build_scheduler_step(module):
    cfg = OmegaConf.structured(TrainConfig(scheduler="step"))
    opt = build_optimizer(module.parameters(), cfg)
    sched = build_scheduler(opt, cfg)
    assert isinstance(sched, torch.optim.lr_scheduler.StepLR)
    assert sched.step_size == cfg.scheduler_step_size
    assert sched.gamma == cfg.scheduler_gamma


def test_build_scheduler_cosine(module):
    cfg = OmegaConf.structured(TrainConfig(scheduler="cosine"))
    opt = build_optimizer(module.parameters(), cfg)
    sched = build_scheduler(opt, cfg)
    assert isinstance(sched, torch.optim.lr_scheduler.CosineAnnealingLR)
    assert sched.T_max == cfg.epochs


def test_build_scheduler_unknown_raises(module):
    cfg = OmegaConf.structured(TrainConfig(scheduler="exponential"))
    opt = build_optimizer(module.parameters(), cfg)
    with pytest.raises(ValueError, match="unknown scheduler"):
        build_scheduler(opt, cfg)
