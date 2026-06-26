"""Tests for the weight-source adapter registry."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch
from omegaconf import OmegaConf

import feral_segmentor.models  # noqa: F401 — triggers source registration
from feral_segmentor.models.source import (
    WeightSource,
    _SOURCES,
    load_model,
    register_source,
)
from feral_segmentor.models.sources.hub import HubSource


def test_hub_registered():
    assert "hub" in _SOURCES
    assert _SOURCES["hub"] is HubSource


def test_register_source_decorator():
    @register_source("_test_dummy_source")
    class _DummySource:
        def load(self, cfg):
            return None

    assert "_test_dummy_source" in _SOURCES
    assert _SOURCES["_test_dummy_source"] is _DummySource
    # Cleanup so other tests see a clean registry.
    del _SOURCES["_test_dummy_source"]


def test_load_model_unknown_raises():
    with pytest.raises(KeyError, match="unknown source"):
        load_model(OmegaConf.create({"source": "bogus"}))


def test_hub_source_satisfies_protocol():
    """HubSource instances are structurally compatible with WeightSource."""
    src: WeightSource = HubSource()
    assert callable(src.load)


def test_hub_source_fetches_and_loads(tmp_path, monkeypatch):
    calls: list[tuple] = []

    def fake_download(repo_id, filename, local_dir):
        calls.append((repo_id, filename, local_dir))
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({}, str(path))
        return str(path)

    monkeypatch.setattr(
        "feral_segmentor.models.sources.hub.hf_hub_download", fake_download
    )

    cfg = OmegaConf.create(
        {
            "source": "hub",
            "repo_id": "org/repo",
            "files": ["weights.pt"],
            "weights_dir": str(tmp_path / "weights"),
            "arch": "net",
        }
    )
    model = load_model(cfg)
    assert model is not None
    assert calls == [("org/repo", "weights.pt", tmp_path / "weights")]
