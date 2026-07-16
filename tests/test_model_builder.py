"""Contract test for models.register_model.model_builder — that it returns a usable model.

Covers only the "local" (in-repo architecture, no network) path, built against the
real Hydra conf/ tree the way tests/test_config_schema.py does. No mock stand-in for
the returned model — calls the real model_builder and asserts on its real object.
"""

from __future__ import annotations

import pytest
import torch
from hydra import compose, initialize
from hydra.core.global_hydra import GlobalHydra
from torch import nn

from feral_vision.config.store import register_configs

# The register_model module already exists; model_builder may still be renamed/moved.
# Guard on the name import (ImportError == "cannot import name 'model_builder'") so
# collection stays green either way.
try:
    from feral_vision.models.register_model import model_builder

    _BUILDER_AVAILABLE = True
except ImportError:
    _BUILDER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _BUILDER_AVAILABLE,
    reason="model_builder not implemented yet (TDD)",
)

# ---------------------------------------------------------------------------
# STEP 1 — SUCCESS CRITERIA
# ---------------------------------------------------------------------------
# model_builder(cfg: DictConfig) -> nn.Module
#
#   C1. Returns an object that is an instance of torch.nn.Module.
#   C2. Calling the returned module on a batched image tensor succeeds without
#       raising and returns a tensor.
#
# Scope: only the "local" (in-repo architecture, no network) path — conf/model/
# base.yaml's default (architecture.source == "local", architecture.id == "net").
# Remote sources (hf_hub/torch_hub/ultralytics/...) are intentionally out of scope
# for this file: none of this repo's deps ship a real mock-server fixture for them.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------

# The resolved "local" architecture is models/default.py's Net (the CIFAR-tutorial
# CNN): fc1 = nn.Linear(16 * 5 * 5, 120) only matches a 5x5 feature map, which its
# conv/pool stack only produces for exactly 32x32 input (32->28->14->10->5). Do not
# change this without checking Net's architecture.
_IMAGE_SIZE = 32


@pytest.fixture(autouse=True)
def _registered():
    """Register Hydra structured configs before each test, as test_config_schema.py does."""
    register_configs()


@pytest.fixture(autouse=True)
def _clear_hydra():
    """Reset Hydra's global state around each test so repeated initialize() calls don't collide."""
    GlobalHydra.instance().clear()
    yield
    GlobalHydra.instance().clear()


def _compose_model_cfg():
    """Compose the real conf/ tree's default model config (architecture.source == 'local')."""
    with initialize(version_base=None, config_path="../conf"):
        cfg = compose(config_name="config")
    return cfg.model


def _batched_image() -> torch.Tensor:
    """One batched RGB image tensor of shape (1, 3, 32, 32) for a forward pass through Net."""
    return torch.rand(1, 3, _IMAGE_SIZE, _IMAGE_SIZE)


# ---------------------------------------------------------------------------
# C1 — returns a usable nn.Module
# ---------------------------------------------------------------------------


def test_model_builder_returns_nn_module():
    """C1: model_builder(cfg.model) returns a torch.nn.Module instance."""
    model = model_builder(_compose_model_cfg())

    assert isinstance(model, nn.Module)


# ---------------------------------------------------------------------------
# C2 — the built model runs a forward pass and returns a tensor
# ---------------------------------------------------------------------------


def test_model_builder_forward_pass_returns_tensor():
    """C2: calling the built module on a batched image tensor returns a tensor."""
    model = model_builder(_compose_model_cfg())

    output = model(_batched_image())

    assert isinstance(output, torch.Tensor)
