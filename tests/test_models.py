"""Tests for the architecture registry and Net default model."""

from __future__ import annotations

import pytest
import torch

import feral_segmentor.models  # noqa: F401 — triggers registration
from feral_segmentor.models.default import Net
from feral_segmentor.models.registry import (
    DEFAULT_ARCH,
    _ARCHITECTURES,
    build_model,
    get_model,
    register,
)


def test_net_registered_as_default():
    assert DEFAULT_ARCH in _ARCHITECTURES
    assert _ARCHITECTURES[DEFAULT_ARCH] is Net


def test_get_model_returns_net():
    model = get_model()
    assert isinstance(model, Net)


def test_get_model_by_name():
    model = get_model("net")
    assert isinstance(model, Net)


def test_get_model_unknown_raises():
    with pytest.raises(KeyError, match="unknown architecture"):
        get_model("does_not_exist")


def test_register_decorator():
    @register("_test_arch")
    class _TinyModel(torch.nn.Module):
        def forward(self, x):
            return x

        @classmethod
        def from_config(cls, cfg):
            return cls()

    from omegaconf import OmegaConf

    cfg = OmegaConf.create({"arch": "_test_arch"})
    model = build_model(cfg)
    assert isinstance(model, _TinyModel)
    del _ARCHITECTURES["_test_arch"]


def test_build_model_unknown_arch_raises():
    from omegaconf import OmegaConf

    with pytest.raises(KeyError, match="unknown architecture"):
        build_model(OmegaConf.create({"arch": "not_real"}))


def test_net_forward_correct_shape():
    model = Net()
    x = torch.randn(2, 3, 32, 32)
    out = model(x)
    assert out.shape == (2, 10)


def test_net_from_config_ignores_cfg():
    from omegaconf import OmegaConf

    cfg = OmegaConf.create({"arch": "net", "unused_field": 99})
    model = Net.from_config(cfg)
    assert isinstance(model, Net)
