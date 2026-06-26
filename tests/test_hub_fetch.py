from pathlib import Path

from omegaconf import OmegaConf

from feral_segmentor.models.hub_fetch import pull_model


def test_pull_model_downloads_each_file(tmp_path, monkeypatch):
    calls = []

    def fake_download(repo_id, filename, local_dir):
        calls.append((repo_id, filename, local_dir))
        return str(Path(local_dir) / filename)

    monkeypatch.setattr(
        "feral_segmentor.models.hub_fetch.hf_hub_download", fake_download
    )

    cfg = OmegaConf.create(
        {
            "repo_id": "org/repo",
            "files": ["a.pt", "b.pth"],
            "weights_dir": str(tmp_path / "weights"),
        }
    )

    paths = pull_model(cfg)

    assert len(paths) == 2
    assert calls == [
        ("org/repo", "a.pt", tmp_path / "weights"),
        ("org/repo", "b.pth", tmp_path / "weights"),
    ]
