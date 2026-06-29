"""Tests for the architecture registry and Net default model."""

from __future__ import annotations

import pytest
import torch
from torch import nn

import feral_segmentor.models  # noqa: F401 — triggers registration
from feral_segmentor.models.registry import (
    _ARCHITECTURES,
    build_model,
    get_model,
    register,
)


def test_get_model_returns_torch_module():
    model = get_model()
    assert isinstance(model, nn.Module)


def test_get_model_by_name():
    model = get_model("net")
    assert isinstance(model, nn.Module)


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
