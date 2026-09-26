"""Behavioral tests for the canonical GPU training-image build entrypoint."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "cloud" / "build_training_image.sh"
VALID_DIGEST = "sha256:" + "a" * 64


def _write_mock_gcloud(path: Path) -> None:
    """Create a deterministic gcloud stub for the image-build control flow."""
    path.write_text(
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >> "$GCLOUD_CALLS"

if [[ "$1" == "auth" && "$2" == "list" ]]; then
  printf '%s\n' 'builder@example.com'
  exit 0
fi

if [[ "$1" == "artifacts" && "$2" == "repositories" && "$3" == "describe" ]]; then
  printf '%s\n' '{}'
  exit 0
fi

if [[ "$1" == "builds" && "$2" == "submit" ]]; then
  exit 0
fi

if [[ "$1" == "artifacts" && "$2" == "docker" && "$3" == "images" && "$4" == "describe" ]]; then
  printf '%s\n' "$MOCK_DIGEST"
  exit 0
fi

printf 'unexpected gcloud call: %s\n' "$*" >&2
exit 64
"""
    )
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, digest: str) -> Path:
    bin_dir = tmp_path / "bin"
    calls = tmp_path / "gcloud-calls.txt"
    bin_dir.mkdir()
    _write_mock_gcloud(bin_dir / "gcloud")
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")
    monkeypatch.setenv("GCLOUD_CALLS", str(calls))
    monkeypatch.setenv("MOCK_DIGEST", digest)
    return calls


def _command() -> list[str]:
    return [
        str(BUILD_SCRIPT),
        "--project",
        "fixture-project",
        "--region",
        "us-east4",
        "--repository",
        "feral-docker",
        "--image",
        "trainer",
        "--tag",
        "candidate",
    ]


def test_build_training_image_submits_canonical_build_and_returns_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls_path = _environment(tmp_path, monkeypatch, VALID_DIGEST)

    result = subprocess.run(
        _command(),
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip().splitlines()[-1] == (
        "us-east4-docker.pkg.dev/fixture-project/feral-docker/trainer@" + VALID_DIGEST
    )

    calls = calls_path.read_text().splitlines()
    assert any(
        call.startswith("artifacts repositories describe feral-docker ")
        and "--location=us-east4" in call
        and "--project=fixture-project" in call
        for call in calls
    )
    assert any(
        call.startswith("builds submit . ")
        and "--config=deploy/cloudbuild.training-image.yaml" in call
        and (
            "--substitutions=_TRAINING_IMAGE="
            "us-east4-docker.pkg.dev/fixture-project/feral-docker/trainer:candidate"
        ) in call
        for call in calls
    )
    assert any(
        call.startswith(
            "artifacts docker images describe "
            "us-east4-docker.pkg.dev/fixture-project/feral-docker/trainer:candidate "
        )
        for call in calls
    )


def test_build_training_image_rejects_non_digest_registry_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _environment(tmp_path, monkeypatch, "not-a-digest")

    result = subprocess.run(
        _command(),
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Artifact Registry returned an invalid digest" in result.stderr
