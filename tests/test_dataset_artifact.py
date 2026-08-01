"""Test Dataset Artifact publication without a live Cloud Storage service."""

from __future__ import annotations

# Standard library imports
import json
from pathlib import Path

# Third-party imports
import pytest
import yaml

# Local imports
from feral_vision.data.dataset_artifact import (
    publish_dataset_artifact,
    publish_dataset_tracker,
)


# ---------------------------------------------------------------------------
# Test doubles


class _MemoryBlob:
    """Use this stand-in to record Cloud Storage blob uploads in memory."""

    def __init__(self) -> None:
        self.filename: str | None = None
        self.text: str | None = None
        self.content_type: str | None = None
        self.options: dict[str, object] = {}

    def upload_from_filename(self, filename: str, **_: object) -> None:
        """Use this method to record a file upload without Cloud Storage."""
        self.filename = filename
        self.options = _

    def upload_from_string(self, data: str, **kwargs: object) -> None:
        """Use this method to record a text upload without Cloud Storage."""
        self.text = data
        self.content_type = kwargs.get("content_type")  # type: ignore[assignment]
        self.options = kwargs


class _MemoryBucket:
    """Use this stand-in to store Cloud Storage blobs in memory."""

    def __init__(self) -> None:
        self.blobs: dict[str, _MemoryBlob] = {}

    def blob(self, blob_name: str) -> _MemoryBlob:
        """Use this method to return the named in-memory blob."""
        return self.blobs.setdefault(blob_name, _MemoryBlob())


class _MemoryStorageClient:
    """Use this stand-in to provide Cloud Storage buckets in memory."""

    def __init__(self) -> None:
        self.buckets: dict[str, _MemoryBucket] = {}

    def bucket(self, bucket_name: str) -> _MemoryBucket:
        """Use this method to return the named in-memory bucket."""
        return self.buckets.setdefault(bucket_name, _MemoryBucket())


# ---------------------------------------------------------------------------
# Fixtures


@pytest.fixture
def payload_root(tmp_path: Path) -> Path:
    """Use this fixture to create a canonical acquisition workspace payload."""
    root = tmp_path / "payload"
    (root / "images").mkdir(parents=True)
    (root / "annotations").mkdir()
    (root / "images" / "animal.jpg").write_bytes(b"image")
    (root / "annotations" / "instances.json").write_text("{}")
    return root


@pytest.fixture
def input_path(tmp_path: Path) -> Path:
    """Use this fixture to create required acquisition provenance metadata."""
    path = tmp_path / "dataset-input.json"
    path.write_text(
        json.dumps(
            {
                "dataset": "Example animal subset",
                "source": "example downloader",
                "provenance": {"query": "animals", "limit": 2},
            }
        )
    )
    return path


# ---------------------------------------------------------------------------
# Publication behavior


def test_publish_dataset_artifact_uploads_payload_and_manifest(
    payload_root: Path, input_path: Path
) -> None:
    """Use this test to verify canonical payload and manifest publication."""
    client = _MemoryStorageClient()

    payload_uri = publish_dataset_artifact(
        client,
        bucket_name="dataset-bucket",
        artifact_prefix="datasets/example/v1",
        payload_root=payload_root,
        input_path=input_path,
    )

    bucket = client.bucket("dataset-bucket")
    assert payload_uri == "gs://dataset-bucket/datasets/example/v1/payload"
    assert set(bucket.blobs) == {
        "datasets/example/v1/payload/images/animal.jpg",
        "datasets/example/v1/payload/annotations/instances.json",
        "datasets/example/v1/dataset-artifact.json",
    }
    manifest = json.loads(bucket.blobs["datasets/example/v1/dataset-artifact.json"].text)
    assert manifest == {
        "schema_version": 1,
        "kind": "Dataset Artifact",
        "dataset": "Example animal subset",
        "source": "example downloader",
        "provenance": {"query": "animals", "limit": 2},
        "payload": {"path": "payload", "file_count": 2},
        "dvc_tracker": {"path": "dataset-artifact.dvc"},
    }
    assert all(blob.options["if_generation_match"] == 0 for blob in bucket.blobs.values())


def test_publish_dataset_artifact_rejects_missing_provenance(
    payload_root: Path, tmp_path: Path
) -> None:
    """Use this test to reject acquisition metadata without provenance."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "Example", "source": "downloader"}))

    with pytest.raises(ValueError, match="provenance"):
        publish_dataset_artifact(
            _MemoryStorageClient(),
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=payload_root,
            input_path=input_path,
        )


def test_publish_dataset_artifact_rejects_noncanonical_payload(
    input_path: Path, tmp_path: Path
) -> None:
    """Use this test to reject a payload missing the annotations directory."""
    payload_root = tmp_path / "payload"
    (payload_root / "images").mkdir(parents=True)

    with pytest.raises(ValueError, match="annotations"):
        publish_dataset_artifact(
            _MemoryStorageClient(),
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=payload_root,
            input_path=input_path,
        )


def test_publish_dataset_tracker_uploads_generated_dvc_file(tmp_path: Path) -> None:
    """Use this test to verify a generated DVC tracker is uploaded."""
    tracker_path = tmp_path / "dataset-artifact.dvc"
    tracker_path.write_text("outs:\n- version_id: 123\n")
    client = _MemoryStorageClient()

    publish_dataset_tracker(
        client,
        bucket_name="dataset-bucket",
        artifact_prefix="datasets/example/v1",
        tracker_path=tracker_path,
    )

    assert client.bucket("dataset-bucket").blobs[
        "datasets/example/v1/dataset-artifact.dvc"
    ].filename == str(tracker_path)


def test_preparation_config_requires_separate_immutable_images() -> None:
    """Use this test to preserve the acquisition-publication image boundary."""
    repository_root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load(
        (repository_root / "deploy/cloudbuild.prepare.yaml").read_text()
    )
    dvc_dockerfile = (repository_root / "deploy/Dockerfile.dvc").read_text().lower()

    assert [step["id"] for step in config["steps"]] == [
        "acquire-coco-into-workspace",
        "publish-dataset-artifact",
    ]
    assert config["steps"][0]["name"] == "${_ACQUISITION_IMAGE}"
    assert config["steps"][1]["name"] == "${_DVC_IMAGE}"
    assert "${_DATASET_ARTIFACT_PREFIX}" in config["steps"][1]["env"][1]
    assert not any(
        dependency in dvc_dockerfile
        for dependency in ("torch", "cuda", "fiftyone", "google-cloud-cli", " uv ")
    )
