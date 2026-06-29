"""Integration tests: build_model from Hydra config resolves to Net."""

from __future__ import annotations

import torch
from hydra import compose, initialize

import feral_segmentor.models  # noqa: F401 — triggers registration
from feral_segmentor.config.store import register_configs
from feral_segmentor.models.default import Net
from feral_segmentor.models.registry import build_model


def _compose(overrides=None):
    """Compose the default Hydra config from the project conf directory."""
    with initialize(version_base=None, config_path="../conf"):
        return compose(config_name="config", overrides=overrides or [])


def test_build_model_from_default_config():
    register_configs()
    cfg = _compose()
    model = build_model(cfg.model)
    assert isinstance(model, Net)


def test_net_forward_from_config():
    register_configs()
    cfg = _compose()
    model = build_model(cfg.model)
    x = torch.randn(1, 3, 32, 32)
    out = model(x)
    assert out.shape == (1, 10)
