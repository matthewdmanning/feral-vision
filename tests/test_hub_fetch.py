"""Tests for the HuggingFace Hub source adapter (HFAdapter)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import torch
from omegaconf import OmegaConf
from feral_segmentor.models.sources.HFAdapter import HFAdapter


def _make_cfg(tmp_path: Path, filenames: list[str]) -> object:
    return OmegaConf.create(
        {
            "architecture": {"source": "hf_hub", "id": "org/repo", "location": None},
            "weights": {
                "source": "hf_hub",
                "id": filenames,
                "location": str(tmp_path / "weights"),
            },
        }
    )


def test_fetch_downloads_each_missing_file(tmp_path, monkeypatch):
    calls: list[tuple] = []

    def fake_download(repo_id, filename, local_dir):
        calls.append((repo_id, filename, str(local_dir)))
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({}, str(path))
        return str(path)

    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter.hf_hub_download", fake_download
    )
    fake_model = MagicMock()
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter._load_local",
        lambda dest, filenames: fake_model,
    )

    cfg = _make_cfg(tmp_path, ["a.pt", "b.pth"])
    model = HFAdapter().fetch(cfg)

    assert model is fake_model
    assert calls == [
        ("org/repo", "a.pt", str(tmp_path / "weights")),
        ("org/repo", "b.pth", str(tmp_path / "weights")),
    ]


def test_fetch_skips_already_cached_file(tmp_path, monkeypatch):
    calls: list[str] = []

    def fake_download(repo_id, filename, local_dir):
        calls.append(filename)
        path = Path(local_dir) / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({}, str(path))
        return str(path)

    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter.hf_hub_download", fake_download
    )
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter._load_local",
        lambda dest, filenames: MagicMock(),
    )

    # Pre-create one file so it should be skipped.
    weights_dir = tmp_path / "weights"
    weights_dir.mkdir(parents=True)
    torch.save({}, str(weights_dir / "a.pt"))

    cfg = _make_cfg(tmp_path, ["a.pt", "b.pth"])
    HFAdapter().fetch(cfg)

    assert calls == ["b.pth"]


def test_fetch_no_weights_uses_direct_load(tmp_path, monkeypatch):
    fake_model = MagicMock()
    monkeypatch.setattr(
        "feral_segmentor.models.sources.HFAdapter._load_direct",
        lambda repo_id: fake_model,
    )

    cfg = OmegaConf.create(
        {
            "architecture": {"source": "hf_hub", "id": "org/repo", "location": None},
            "weights": None,
        }
    )
    model = HFAdapter().fetch(cfg)
    assert model is fake_model
