"""Test Dataset Artifact publication: payload and file manifest."""

from __future__ import annotations

import hashlib
import itertools
import json
import os
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from feral_vision.data.dataset_artifact import publish_dataset_artifact


class _MemoryBlob:
    """In-memory stand-in for a Cloud Storage object upload."""

    def __init__(self, generations: Iterator[int]) -> None:
        self._generations = generations
        self.filename: str | None = None
        self.data: str | None = None
        self.generation: int | None = None
        self.options: dict[str, object] = {}
        self.retention = SimpleNamespace(mode=None, retain_until_time=None)

    def upload_from_filename(self, filename: str, **kwargs: object) -> None:
        """Use this method to record a file upload without Cloud Storage."""
        self.filename = filename
        self.generation = next(self._generations)
        self.options = kwargs

    def upload_from_string(self, data: str, **kwargs: object) -> None:
        """Use this method to record a string upload without Cloud Storage."""
        self.data = data
        self.generation = next(self._generations)
        self.options = kwargs


class _MemoryBucket:
    """In-memory collection of Cloud Storage objects."""

    def __init__(self) -> None:
        self.blobs: dict[str, _MemoryBlob] = {}
        self._generations = itertools.count(1)

    def blob(self, blob_name: str) -> _MemoryBlob:
        """Use this method to retrieve one in-memory Cloud Storage object."""
        return self.blobs.setdefault(blob_name, _MemoryBlob(self._generations))


class _MemoryStorageClient:
    """In-memory Cloud Storage client for Dataset Artifact tests."""

    def __init__(self) -> None:
        self.buckets: dict[str, _MemoryBucket] = {}

    def bucket(self, bucket_name: str) -> _MemoryBucket:
        """Use this method to retrieve one in-memory Cloud Storage bucket."""
        return self.buckets.setdefault(bucket_name, _MemoryBucket())


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
    dataset_root: Path, tmp_path: Path
) -> None:
    """Every payload file is published, and the manifest is published last."""
    (dataset_root / "images" / "a.jpg").write_bytes(b"jpg")
    (dataset_root / "annotations" / "instances.json").write_text("{}")
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "example", "source": "test"}))
    client = _MemoryStorageClient()

    uri = publish_dataset_artifact(
        client,
        bucket_name="dataset-bucket",
        artifact_prefix="/datasets/example/v1/",
        payload_root=dataset_root,
        input_path=input_path,
        retention_days=30,
    )

    assert uri == f"{os.environ['GCS_URI_PREFIX']}dataset-bucket/datasets/example/v1"
    blobs = client.bucket("dataset-bucket").blobs
    assert list(blobs) == [
        "datasets/example/v1/payload/annotations/instances.json",
        "datasets/example/v1/payload/images/a.jpg",
        "datasets/example/v1/dataset-artifact.json",
    ]
    image = blobs["datasets/example/v1/payload/images/a.jpg"]
    assert image.options == {"if_generation_match": 0}
    assert image.retention.mode == "Unlocked"
    assert image.retention.retain_until_time is not None
    manifest = blobs["datasets/example/v1/dataset-artifact.json"]
    assert json.loads(manifest.data or "") == {
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
    assert manifest.options["if_generation_match"] == 0
    assert manifest.retention.mode == "Unlocked"


def test_publish_dataset_artifact_rejects_empty_input(
    dataset_root: Path, tmp_path: Path
) -> None:
    """A Dataset without provenance input is not published."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text("{}")
    client = _MemoryStorageClient()

    with pytest.raises(ValueError, match="non-empty JSON object"):
        publish_dataset_artifact(
            client,
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=dataset_root,
            input_path=input_path,
            retention_days=30,
        )

    assert client.buckets == {}


def test_publish_dataset_artifact_rejects_input_that_defines_files(
    dataset_root: Path, tmp_path: Path
) -> None:
    """The publisher alone writes the file listing of a manifest."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "example", "files": {}}))

    with pytest.raises(ValueError, match="must not define files"):
        publish_dataset_artifact(
            _MemoryStorageClient(),
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            payload_root=dataset_root,
            input_path=input_path,
            retention_days=30,
        )


def test_publish_dataset_artifact_rejects_zero_retention(
    dataset_root: Path, tmp_path: Path
) -> None:
    """A Dataset Artifact is always published with object retention."""
    input_path = tmp_path / "dataset-input.json"
    input_path.write_text(json.dumps({"dataset": "example"}))

    with pytest.raises(ValueError, match="at least one day"):
        publish_dataset_artifact(
            _MemoryStorageClient(),
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
    dvc_dockerfile = (repository_root / "deploy/Dockerfile.dvc").read_text().lower()

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
