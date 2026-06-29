"""Tests for HFAdapter fetch/inspect and the register_model registry workflow."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch
import torch.nn as nn
from omegaconf import OmegaConf

from feral_segmentor.models.sources.HFAdapter import HFAdapter


def _cfg(tmp_path, filenames=("weights.pt",), location="weights"):
    return OmegaConf.create(
        {
            "architecture": {"source": "hf_hub", "id": "org/repo", "location": None},
            "weights": {
                "source": "hf_hub",
                "id": list(filenames),
                "location": str(tmp_path / location) if location else None,
            },
        }
    )


def _cfg_no_weights(tmp_path):
    return OmegaConf.create(
        {
            "architecture": {"source": "hf_hub", "id": "org/repo", "location": None},
            "weights": None,
        }
    )


# --- fetch -------------------------------------------------------------------


def test_fetch_downloads_missing_files(tmp_path, monkeypatch):
    calls = []

    def fake_download(repo_id, filename, local_dir):
        calls.append((repo_id, filename, local_dir))
        p = Path(local_dir) / filename
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save(nn.Linear(4, 2), str(p))

    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter.hf_hub_download", fake_download
    )
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter._load_local",
        lambda dest, filenames: nn.Linear(4, 2),
    )
    HFAdapter().fetch(_cfg(tmp_path))
    assert calls == [("org/repo", "weights.pt", tmp_path / "weights")]


def test_fetch_skips_existing_files(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter.hf_hub_download",
        lambda **kw: calls.append(kw),
    )
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    (weights_dir / "weights.pt").touch()

    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter._load_local",
        lambda dest, filenames: nn.Linear(4, 2),
    )
    HFAdapter().fetch(_cfg(tmp_path))
    assert calls == []


def test_fetch_returns_module(tmp_path):
    model = nn.Linear(4, 2)
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir()
    torch.save(model, str(weights_dir / "weights.pt"))

    result = HFAdapter().fetch(_cfg(tmp_path))
    assert isinstance(result, nn.Module)


def test_fetch_null_location_loads_direct(tmp_path, monkeypatch):
    loaded = nn.Linear(4, 2)
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter._load_direct",
        lambda repo_id: loaded,
    )
    result = HFAdapter().fetch(_cfg_no_weights(tmp_path))
    assert result is loaded


# --- inspect -----------------------------------------------------------------


def test_inspect_raises_on_hub_failure_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter.model_info",
        lambda repo_id: (_ for _ in ()).throw(Exception("unreachable")),
    )
    with pytest.raises(RuntimeError, match="fetch_if_needed"):
        HFAdapter().inspect(_cfg(tmp_path))


def test_inspect_returns_properties_from_metadata(tmp_path, monkeypatch):
    class FakeInfo:
        pipeline_tag = "pose-estimation"
        config = {"num_labels": 17}

    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter.model_info",
        lambda repo_id: FakeInfo(),
    )
    from feral_segmentor.tasks import CVTask

    props, meta = HFAdapter().inspect(_cfg(tmp_path))
    assert props.model_outputs == [CVTask.POSE]
    assert meta["pipeline_tag"] == "pose-estimation"
