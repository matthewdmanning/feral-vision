"""Test Dataset Artifact publication: payload and file manifest."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import Mock, call, create_autospec

import pytest
import yaml
from google.cloud import storage

from feral_vision.data.dataset_artifact import publish_dataset_artifact


@pytest.fixture
def storage_client():
    """Provide an API-checked Cloud Storage client without credentials or network I/O."""
    return create_autospec(storage.Client, instance=True, spec_set=True)


@pytest.fixture(autouse=True)
def _storage_uri_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use this fixture to isolate publication from operator URI configuration."""
    monkeypatch.setenv("GCS_URI_PREFIX", "test-storage://")


@pytest.fixture
def dataset_root(tmp_path: Path) -> Path:
    """Use this fixture when a test needs a canonical acquired Dataset folder."""
    root = tmp_path / "payload"
    (root / "images").mkdir(parents=True)
    (root / "annotations").mkdir()
    return root


def test_publish_dataset_artifact_uploads_payload_then_manifest(
    dataset_root: Path, tmp_path: Path, storage_client
) -> None:
    """Every payload file is published, and the manifest is published last."""
    (dataset_root / "images" / "a.jpg").write_bytes(b"jpg")
    (dataset_root / "annotations" / "instances.json").write_text("{}")
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "example", "source": "test"}))
    bucket = create_autospec(storage.Bucket, instance=True, spec_set=True)
    blobs = [
        create_autospec(storage.Blob, instance=True, spec_set=True) for _ in range(3)
    ]
    for generation, blob in enumerate(blobs, start=1):
        blob.generation = generation
        blob.retention.mode = None
        blob.retention.retain_until_time = None
    bucket.blob.side_effect = blobs
    storage_client.bucket.return_value = bucket
    uploads = Mock()
    uploads.attach_mock(blobs[0].upload_from_filename, "annotation")
    uploads.attach_mock(blobs[1].upload_from_filename, "image")
    uploads.attach_mock(blobs[2].upload_from_string, "manifest")

    uri = publish_dataset_artifact(
        storage_client,
        bucket_name="dataset-bucket",
        artifact_prefix="/datasets/example/v1/",
        payload_root=dataset_root,
        input_path=input_path,
        retention_days=30,
    )

    assert uri == f"{os.environ['GCS_URI_PREFIX']}dataset-bucket/datasets/example/v1"
    storage_client.bucket.assert_called_once_with("dataset-bucket")
    assert bucket.blob.call_args_list == [
        call("datasets/example/v1/payload/annotations/instances.json"),
        call("datasets/example/v1/payload/images/a.jpg"),
        call("datasets/example/v1/dataset-artifact.json"),
    ]
    assert [upload[0] for upload in uploads.mock_calls] == [
        "annotation",
        "image",
        "manifest",
    ]
    image = blobs[1]
    image.upload_from_filename.assert_called_once_with(
        str(dataset_root / "images" / "a.jpg"), if_generation_match=0
    )
    assert image.retention.mode == "Unlocked"
    assert image.retention.retain_until_time is not None
    manifest = blobs[2]
    manifest.upload_from_string.assert_called_once()
    upload = manifest.upload_from_string.call_args
    assert json.loads(upload.args[0]) == {
        "dataset": "example",
        "source": "test",
        "files": {
            "annotations/instances.json": {
                "generation": 1,
                "sha256": hashlib.sha256(b"{}").hexdigest(),
            },
            "images/a.jpg": {
                "generation": 2,
                "sha256": hashlib.sha256(b"jpg").hexdigest(),
            },
        },
    }
    assert upload.kwargs == {
        "content_type": "application/json",
        "if_generation_match": 0,
    }
    assert manifest.retention.mode == "Unlocked"


def test_publish_dataset_artifact_rejects_empty_input(
    dataset_root: Path, tmp_path: Path, storage_client
) -> None:
    """A Dataset without provenance input is not published."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text("{}")

    with pytest.raises(ValueError, match="non-empty JSON object"):
        publish_dataset_artifact(
            storage_client,
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=dataset_root,
            input_path=input_path,
            retention_days=30,
        )

    storage_client.bucket.assert_not_called()


def test_publish_dataset_artifact_rejects_input_that_defines_files(
    dataset_root: Path, tmp_path: Path, storage_client
) -> None:
    """The publisher alone writes the file listing of a manifest."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "example", "files": {}}))

    with pytest.raises(ValueError, match="must not define files"):
        publish_dataset_artifact(
            storage_client,
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=dataset_root,
            input_path=input_path,
            retention_days=30,
        )


def test_publish_dataset_artifact_rejects_zero_retention(
    dataset_root: Path, tmp_path: Path, storage_client
) -> None:
    """A Dataset Artifact is always published with object retention."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "example"}))

    with pytest.raises(ValueError, match="at least one day"):
        publish_dataset_artifact(
            storage_client,
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=dataset_root,
            input_path=input_path,
            retention_days=0,
        )


def test_publication_script_publishes_without_dvc() -> None:
    """The Cloud Job publishes the payload and manifest with no DVC command."""
    repository_root = Path(__file__).resolve().parents[1]
    script = (repository_root / "scripts/cloud/publish_dataset_artifact.sh").read_text()

    assert "publish_dataset_artifact(" in script
    assert "dvc" not in script


def test_preparation_config_requires_separate_immutable_images() -> None:
    """Acquisition and DVC publication remain separate Cloud Build steps."""
    repository_root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (repository_root / "deploy/cloudbuild.prepare.yaml").read_text()
    )
    dvc_dockerfile = (
        (repository_root / "deploy/dataset-publisher/Dockerfile").read_text().lower()
    )

    assert [step["id"] for step in config["steps"]] == [
        "acquire-dataset-into-workspace",
        "publish-dataset-artifact",
    ]
    assert config["steps"][0]["name"] == "${_ACQUISITION_IMAGE}"
    assert config["steps"][1]["name"] == "${_DVC_IMAGE}"
    assert "${_DATASET_ARTIFACT_PREFIX}" in config["steps"][1]["env"][1]
    assert not any(
        dependency in dvc_dockerfile
        for dependency in ("torch", "cuda", "fiftyone", "google-cloud-cli", " uv ")
    )
