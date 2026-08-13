"""Verify the Bash image-operation script submits a configured Cloud Build."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess

import pytest


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_IMAGE_OPERATIONS_SCRIPT = _REPOSITORY_ROOT / "scripts/cloud/image_operations.sh"


def _write_mock_command(command_path: Path) -> None:
    """Use this helper to record an image-operation command and its configured environment."""
    command_path.write_text(
        "#!/usr/bin/env bash\n"
        "printf '%s|%s|%s|%s|%s|%s|%s|%s\\n' "
        '"$GCP_PROJECT" "$REGISTRY_REGION" "$ARTIFACT_REPOSITORY" '
        '"$BASE_IMAGE_NAME" "$TRAINING_IMAGE_NAME" "$IMAGE_TAG" '
        '"$IMAGE_URI" "$*" > "$IMAGE_OPERATION_OUTPUT"\n'
    )
    command_path.chmod(command_path.stat().st_mode | stat.S_IXUSR)


def _deployment_config(config_path: Path) -> None:
    """Use this helper to create the smallest deployment YAML consumed by the Bash dispatcher."""
    config_path.write_text(
        "substitutions:\n"
        "  _GCP_PROJECT: fixture-project\n"
        "  _REGION: fixture-region\n"
        "  _REPO: fixture-repository\n"
        "  _BASE_IMAGE_NAME: fixture-base\n"
        "  _IMAGE_NAME: fixture-training\n"
        "  _IMAGE_TAG: fixture-tag\n"
    )


def test_image_operations_submits_configured_cloud_build(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use this test to submit one configured Cloud Build without exporting deployment values."""
    deployment_config_file = tmp_path / "deployment.yaml"
    command_directory = tmp_path / "bin"
    command_output = tmp_path / "command-output.txt"
    command_directory.mkdir()
    _deployment_config(deployment_config_file)
    _write_mock_command(command_directory / "gcloud")
    monkeypatch.setenv("PATH", f"{command_directory}:{os.environ['PATH']}")
    monkeypatch.setenv("IMAGE_OPERATION_OUTPUT", str(command_output))

    subprocess.run(
        [
            _IMAGE_OPERATIONS_SCRIPT,
            "--config",
            str(deployment_config_file),
        ],
        check=True,
    )

    assert command_output.read_text().strip() == (
        "|||||||"
        "builds submit . --project=fixture-project --region=fixture-region --quiet "
        "--config=deploy/cloudbuild.build.yaml "
        "--substitutions=_REGION=fixture-region,_REPO=fixture-repository,"
        "_BASE_IMAGE_NAME=fixture-base,_IMAGE_NAME=fixture-training,_IMAGE_TAG=fixture-tag"
    )
