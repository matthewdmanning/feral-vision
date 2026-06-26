from pathlib import Path

import pytest
import torch
from omegaconf import OmegaConf

from feral_segmentor.constants import (
    DEFAULT_BASE_CHANNELS,
    DEFAULT_IN_CHANNELS,
    DEFAULT_NUM_CLASSES,
)
from feral_segmentor.models.source import (
    ConfigModelSource,
    HubModelSource,
    ScriptModelSource,
    build_model_source,
)


def _arch_fields():
    return {
        "in_channels": DEFAULT_IN_CHANNELS,
        "base_channels": DEFAULT_BASE_CHANNELS,
        "num_classes": DEFAULT_NUM_CLASSES,
    }


def test_build_model_source_dispatch():
    assert isinstance(
        build_model_source(OmegaConf.create({"source": "hub"})), HubModelSource
    )
    assert isinstance(
        build_model_source(OmegaConf.create({"source": "script"})), ScriptModelSource
    )
    assert isinstance(
        build_model_source(OmegaConf.create({"source": "config"})), ConfigModelSource
    )


def test_build_model_source_unknown_raises():
    with pytest.raises(KeyError):
        build_model_source(OmegaConf.create({"source": "bogus"}))


def test_hub_source_calls_pull_model(tmp_path, monkeypatch):
    calls = []

    def fake_download(repo_id, filename, local_dir):
        calls.append((repo_id, filename, local_dir))
        return str(Path(local_dir) / filename)

    monkeypatch.setattr(
        "feral_segmentor.models.hub_fetch.hf_hub_download", fake_download
    )

    cfg = OmegaConf.create(
        {
            "source": "hub",
            "repo_id": "org/repo",
            "files": ["a.pt"],
            "weights_dir": str(tmp_path / "weights"),
        }
    )
    paths = build_model_source(cfg).acquire(cfg)
    assert len(paths) == 1
    assert calls == [("org/repo", "a.pt", tmp_path / "weights")]


def test_script_source_runs_entrypoint(tmp_path):
    weights_dir = tmp_path / "script_weights"
    cfg = OmegaConf.create(
        {
            "source": "script",
            "name": "student_script",
            "entrypoint": "feral_segmentor.models.example_export:export",
            "weights_dir": str(weights_dir),
            **_arch_fields(),
        }
    )
    paths = build_model_source(cfg).acquire(cfg)
    assert len(paths) == 1
    assert paths[0].exists()


def test_script_source_bad_entrypoint_format_raises(tmp_path):
    cfg = OmegaConf.create({"source": "script", "entrypoint": "no_colon_here"})
    with pytest.raises(ValueError):
        build_model_source(cfg).acquire(cfg)


def test_script_source_missing_attr_raises(tmp_path):
    cfg = OmegaConf.create(
        {
            "source": "script",
            "entrypoint": "feral_segmentor.models.example_export:does_not_exist",
        }
    )
    with pytest.raises(AttributeError):
        build_model_source(cfg).acquire(cfg)


def test_config_source_builds_and_saves(tmp_path):
    weights_dir = tmp_path / "cfg_weights"
    cfg = OmegaConf.create(
        {
            "source": "config",
            "name": "student_default",
            "weights_dir": str(weights_dir),
            **_arch_fields(),
        }
    )
    paths = build_model_source(cfg).acquire(cfg)
    assert len(paths) == 1
    assert paths[0].exists()
    # Saved object is a loadable state_dict.
    state = torch.load(paths[0])
    assert isinstance(state, dict)
