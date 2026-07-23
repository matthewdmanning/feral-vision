"""Verify training builders instantiate every selectable Hydra component."""

from __future__ import annotations

from pathlib import Path

# third-party
import pytest
import torch
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from hydra.utils import get_class
from omegaconf import DictConfig

# project
from feral_vision.config.store import register_configs
from feral_vision.training.optim import (
    build_loss_fn,
    build_optimizer,
    build_scheduler,
)


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------

_CONF_ROOT = Path(__file__).resolve().parents[1] / "conf"


def _variant_names(group: str) -> tuple[str, ...]:
    """Return selectable YAML variant names for one training component group."""
    return tuple(path.stem for path in sorted((_CONF_ROOT / group).glob("*.yaml")))


def _compose_training_cfg(override: str) -> DictConfig:
    """Compose the smoke Run Recipe with one real training-component override."""
    with initialize(version_base=None, config_path="../conf"):
        return compose(config_name="runs/smoke", overrides=[override])


@pytest.fixture(autouse=True)
def _registered_and_isolated_hydra() -> None:
    """Register schemas and clear global Hydra state around each composition."""
    register_configs()
    GlobalHydra.instance().clear()
    yield
    GlobalHydra.instance().clear()


@pytest.fixture(params=_variant_names("train/optim"))
def optimizer_cfg(request: pytest.FixtureRequest) -> DictConfig:
    """Provide each selectable optimizer configuration from the real config tree."""
    return _compose_training_cfg(f"train/optim={request.param}").train.optim


@pytest.fixture(params=_variant_names("train/scheduler"))
def scheduler_cfg(request: pytest.FixtureRequest) -> DictConfig:
    """Provide each selectable scheduler configuration from the real config tree."""
    return _compose_training_cfg(f"train/scheduler={request.param}").train.scheduler


@pytest.fixture(params=_variant_names("train/loss_fn"))
def loss_cfg(request: pytest.FixtureRequest) -> DictConfig:
    """Provide each selectable loss configuration from the real config tree."""
    return _compose_training_cfg(f"train/loss_fn={request.param}").train.loss_fn


# ---------------------------------------------------------------------------
# Optimizers and schedulers
# ---------------------------------------------------------------------------


def test_build_optimizer_binds_real_variant_and_updates_image_model(
    image_model: torch.nn.Module, optimizer_cfg: DictConfig
) -> None:
    optimizer = build_optimizer(image_model.parameters(), optimizer_cfg)
    parameters_before = [
        parameter.detach().clone() for parameter in image_model.parameters()
    ]

    image_model(torch.ones(1, 3, 8, 8)).square().mean().backward()
    optimizer.step()

    assert isinstance(optimizer, get_class(optimizer_cfg._target_))
    assert any(
        not torch.equal(before, after)
        for before, after in zip(parameters_before, image_model.parameters())
    )


def test_build_scheduler_binds_every_real_variant(
    image_model: torch.nn.Module, scheduler_cfg: DictConfig
) -> None:
    optimizer_cfg = _compose_training_cfg("train/optim=adam").train.optim
    optimizer = build_optimizer(image_model.parameters(), optimizer_cfg)

    scheduler = build_scheduler(optimizer, scheduler_cfg)

    assert isinstance(scheduler, get_class(scheduler_cfg._target_))
    assert scheduler.optimizer is optimizer


def test_build_scheduler_none_disables_scheduling(image_model: torch.nn.Module) -> None:
    optimizer_cfg = _compose_training_cfg("train/optim=adam").train.optim
    optimizer = build_optimizer(image_model.parameters(), optimizer_cfg)

    assert build_scheduler(optimizer, None) is None


# ---------------------------------------------------------------------------
# Loss functions
# ---------------------------------------------------------------------------


def test_build_loss_fn_instantiates_every_real_variant(loss_cfg: DictConfig) -> None:
    loss_fn = build_loss_fn(loss_cfg)

    assert isinstance(loss_fn, get_class(loss_cfg._target_))
