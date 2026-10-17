"""Verify prepared Datasets can be independently registered and restored with DVC."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REGISTER_SCRIPT = REPOSITORY_ROOT / "feral-vision/scripts/data/register.sh"

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def dvc_repo(tmp_path: Path) -> Path:
    """Use this function when registration needs a real repository and local remote."""
    repo = tmp_path / "repo"
    repo.mkdir()
    for command in (
        ["git", "init", "-q"],
        ["dvc", "init", "-q"],
        ["dvc", "remote", "add", "--default", "test", str(tmp_path / "remote")],
    ):
        subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)
    shutil.copyfile(REPOSITORY_ROOT / ".gitignore", repo / ".gitignore")
    dockerfile = repo / "deploy/dataset-publisher/Dockerfile"
    dockerfile.parent.mkdir(parents=True)
    shutil.copyfile(
        REPOSITORY_ROOT / "feral-vision/deploy/dataset-publisher/Dockerfile", dockerfile
    )
    return repo


# ---------------------------------------------------------------------------
# Dataset registration and recovery
# ---------------------------------------------------------------------------


def test_register_restores_selected_dataset_without_tracking_other_data(
    dvc_repo: Path,
) -> None:
    """Use this function to verify Dataset selection, durable upload, and recovery."""
    selected = dvc_repo / "data/augmented/selected"
    (selected / "images").mkdir(parents=True)
    (selected / "annotations").mkdir()
    image_bytes = (REPOSITORY_ROOT / "tests/fixtures/test_image.jpg").read_bytes()
    label = "0 0.5 0.5 0.2 0.2\n"
    (selected / "images/sample.jpg").write_bytes(image_bytes)
    (selected / "annotations/sample.txt").write_text(label)
    unrelated = dvc_repo / "data/raw/unrelated.txt"
    unrelated.parent.mkdir()
    unrelated.write_text("keep me")

    subprocess.run(
        ["bash", str(REGISTER_SCRIPT), str(selected)],
        cwd=dvc_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    metadata = selected.with_suffix(".dvc")
    original_metadata = metadata.read_bytes()
    assert not (dvc_repo / "dvc.lock").exists()
    assert list(dvc_repo.glob("data/**/*.dvc")) == [metadata]
    tracked = subprocess.run(
        ["git", "check-ignore", str(metadata)],
        cwd=dvc_repo,
        capture_output=True,
        check=False,
    )
    assert tracked.returncode == 1
    subprocess.run(
        ["bash", str(REGISTER_SCRIPT), str(selected)],
        cwd=dvc_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert metadata.read_bytes() == original_metadata

    shutil.rmtree(selected)
    shutil.rmtree(dvc_repo / ".dvc/cache")
    subprocess.run(
        ["dvc", "pull", str(metadata)],
        cwd=dvc_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert (selected / "images/sample.jpg").read_bytes() == image_bytes
    assert (selected / "annotations/sample.txt").read_text() == label
    assert unrelated.read_text() == "keep me"
    status = subprocess.run(
        ["dvc", "status", "--json"],
        cwd=dvc_repo,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == "{}"


@pytest.mark.parametrize("invalid_input", ["missing_annotations", "outside_repository"])
def test_register_rejects_invalid_dataset_before_recording_metadata(
    dvc_repo: Path, tmp_path: Path, invalid_input: str
) -> None:
    """Use this function to prevent accidental registration of an invalid folder."""
    root = (
        tmp_path / "outside"
        if invalid_input == "outside_repository"
        else dvc_repo / "incomplete"
    )
    (root / "images").mkdir(parents=True)
    if invalid_input == "outside_repository":
        (root / "annotations").mkdir()
    result = subprocess.run(
        ["bash", str(REGISTER_SCRIPT), str(root)],
        cwd=dvc_repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert not root.with_suffix(".dvc").exists()
    assert not (dvc_repo / ".dvc/cache").exists()
