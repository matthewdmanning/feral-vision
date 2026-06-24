"""Standalone tests for the config-driven segmentation pipeline.

All cross-unit collaborators (fetch_data, load_image, preprocess, build_model,
build_model_source) are monkeypatched so ``segment`` runs without real data,
models, or weights.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from omegaconf import OmegaConf

from feral_segmentor import pipeline


class DummyOutput:
    """Stand-in for SegmentationOutput (duck-typed)."""

    def __init__(self, tag: str):
        self.tag = tag


class DummyModel:
    def __init__(self):
        self.loaded_state = None
        self.predicted_with = None

    def load_state_dict(self, state_dict):
        self.loaded_state = state_dict

    def predict(self, image):
        self.predicted_with = image
        return DummyOutput("predicted")


class DummySource:
    def __init__(self, checkpoint):
        self._checkpoint = checkpoint
        self.acquired_with = None

    def acquire(self, model_cfg):
        self.acquired_with = model_cfg
        return self._checkpoint


def _make_cfg(root: str = "data/root", source: str = "local"):
    return OmegaConf.create(
        {
            "data": {"source": source, "root": root},
            "model": {"name": "dummy", "source": "config"},
        }
    )


@pytest.fixture
def wired(monkeypatch):
    """Wire dummy collaborators; return the captured calls and dummy model."""
    calls: dict[str, object] = {}
    model = DummyModel()
    source = DummySource(checkpoint=None)

    def fake_fetch_data(src):
        calls["fetch"] = src
        return Path("fetched/image.png")

    def fake_load_image(path):
        calls["load"] = path
        return "raw-image"

    def fake_preprocess(image):
        calls["preprocess"] = image
        return "tensor"

    def fake_build_model(model_cfg):
        calls["build_model"] = model_cfg
        return model

    def fake_build_model_source(model_cfg):
        calls["build_source"] = model_cfg
        return source

    monkeypatch.setattr(pipeline, "fetch_data", fake_fetch_data)
    monkeypatch.setattr(pipeline, "load_image", fake_load_image)
    monkeypatch.setattr(pipeline, "preprocess", fake_preprocess)
    monkeypatch.setattr(pipeline, "build_model", fake_build_model)
    monkeypatch.setattr(pipeline, "build_model_source", fake_build_model_source)

    return {"calls": calls, "model": model, "source": source}


def test_segment_returns_model_prediction(wired):
    cfg = _make_cfg()
    output = pipeline.segment(cfg)
    assert isinstance(output, DummyOutput)
    assert output.tag == "predicted"


def test_segment_runs_full_chain(wired):
    cfg = _make_cfg(root="data/root")
    pipeline.segment(cfg)

    calls = wired["calls"]
    assert calls["fetch"] == "data/root"
    assert calls["load"] == Path("fetched/image.png")
    assert calls["preprocess"] == "raw-image"
    assert wired["model"].predicted_with == "tensor"


def test_segment_uses_data_source_when_no_root(wired):
    cfg = _make_cfg(root="", source="remote-bucket")
    pipeline.segment(cfg)
    assert wired["calls"]["fetch"] == "remote-bucket"


def test_segment_skips_weight_load_without_checkpoint(wired):
    cfg = _make_cfg()
    pipeline.segment(cfg)
    assert wired["model"].loaded_state is None
    assert wired["source"].acquired_with is cfg.model


def test_segment_loads_checkpoint_when_present(monkeypatch, wired, tmp_path):
    ckpt = tmp_path / "model.pt"
    ckpt.write_bytes(b"placeholder")
    wired["source"]._checkpoint = str(ckpt)

    sentinel_state = {"weights": 1}
    monkeypatch.setattr(
        pipeline.torch, "load", lambda p, map_location=None: sentinel_state
    )

    cfg = _make_cfg()
    pipeline.segment(cfg)

    assert wired["model"].loaded_state == sentinel_state


def test_segment_skips_missing_checkpoint_path(wired):
    wired["source"]._checkpoint = "does/not/exist.pt"
    cfg = _make_cfg()
    pipeline.segment(cfg)
    assert wired["model"].loaded_state is None


def test_main_is_importable():
    import importlib

    main_mod = importlib.import_module("feral_segmentor.main")

    assert callable(main_mod.main)
    assert main_mod._flatten_params({"a": {"b": 1}, "c": 2}) == {"a.b": 1, "c": 2}
