"""Tests for the HuggingFace Hub weight-source adapter."""

from __future__ import annotations

from pathlib import Path

import torch
from omegaconf import OmegaConf

import feral_segmentor.models  # noqa: F401 — triggers registration
from feral_segmentor.models.sources.hub import HubSource


def test_hub_source_downloads_each_file(tmp_path, monkeypatch):
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
            "repo_id": "org/repo",
            "files": ["a.pt", "b.pth"],
            "weights_dir": str(tmp_path / "weights"),
            "arch": "net",
        }
    )

    model = HubSource().load(cfg)

    assert model is not None
    assert calls == [
        ("org/repo", "a.pt", tmp_path / "weights"),
        ("org/repo", "b.pth", tmp_path / "weights"),
    ]


def test_hub_source_no_files_returns_model(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "feral_segmentor.models.sources.hub.hf_hub_download",
        lambda **kw: str(tmp_path / "x.pt"),
    )

    cfg = OmegaConf.create(
        {
            "repo_id": "org/repo",
            "files": [],
            "weights_dir": str(tmp_path / "weights"),
            "arch": "net",
        }
    )
    model = HubSource().load(cfg)
    assert model is not None
