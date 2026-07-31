"""Verify the configured local model builds and processes batched 2D images."""

from __future__ import annotations

# third-party
import pytest
import torch
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from omegaconf import DictConfig
from torch import nn

# project
from feral_vision.config.store import register_configs
from feral_vision.models.register_model import model_builder


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _registered_and_isolated_hydra() -> None:
    """Register schemas and clear global Hydra state around recipe composition."""
    register_configs()
    GlobalHydra.instance().clear()
    yield
    GlobalHydra.instance().clear()


@pytest.fixture
def local_model_cfg() -> DictConfig:
    """Compose the smoke recipe's local in-repository model configuration."""
    with initialize(version_base=None, config_path="../conf"):
        return compose(config_name="runs/smoke").model


@pytest.fixture
def built_local_model(local_model_cfg: DictConfig) -> nn.Module:
    """Build the configured local model and release its gradient state afterward."""
    model = model_builder(local_model_cfg)
    yield model
    model.zero_grad(set_to_none=True)
    model.to("cpu")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@pytest.fixture(params=[1, 3, 10])
def local_model_input(request: pytest.FixtureRequest) -> torch.Tensor:
    """Provide supported 32x32 RGB batches across representative batch sizes."""
    return torch.ones(request.param, 3, 32, 32)


# ---------------------------------------------------------------------------
# Local model construction
# ---------------------------------------------------------------------------


def test_model_builder_builds_local_model_with_batched_logits(
    built_local_model: nn.Module, local_model_input: torch.Tensor
) -> None:
    output = built_local_model(local_model_input)

    assert isinstance(built_local_model, nn.Module)
    assert isinstance(output, torch.Tensor)
    assert output.shape == (local_model_input.shape[0], 10)
