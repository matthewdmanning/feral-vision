"""Test DVC Dataset-folder version records and their lockfile publication."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from feral_vision.data import dataset_artifact
from feral_vision.data.dataset_artifact import publish_dataset_lock, version_dataset


class _MemoryBlob:
    """In-memory stand-in for a Cloud Storage object upload."""

    def __init__(self) -> None:
        self.filename: str | None = None
        self.options: dict[str, object] = {}

    def upload_from_filename(self, filename: str, **kwargs: object) -> None:
        """Use this method to record a lockfile upload without Cloud Storage."""
        self.filename = filename
        self.options = kwargs


class _MemoryBucket:
    """In-memory collection of Cloud Storage objects."""

    def __init__(self) -> None:
        self.blobs: dict[str, _MemoryBlob] = {}

    def blob(self, blob_name: str) -> _MemoryBlob:
        """Use this method to retrieve one in-memory Cloud Storage object."""
        return self.blobs.setdefault(blob_name, _MemoryBlob())


class _MemoryStorageClient:
    """In-memory Cloud Storage client for Dataset lockfile tests."""

    def __init__(self) -> None:
        self.buckets: dict[str, _MemoryBucket] = {}

    def bucket(self, bucket_name: str) -> _MemoryBucket:
        """Use this method to retrieve one in-memory Cloud Storage bucket."""
        return self.buckets.setdefault(bucket_name, _MemoryBucket())


@pytest.fixture
def dataset_root(tmp_path: Path) -> Path:
    """Use this fixture when a test needs a canonical acquired Dataset folder."""
    root = tmp_path / "payload"
    (root / "images").mkdir(parents=True)
    (root / "annotations").mkdir()
    return root


def test_version_dataset_records_folder_in_lockfile(
    dataset_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Dataset folder is added, recorded by a DVC stage, then reproduced."""
    commands: list[list[str]] = []

    def fake_run(command: list[str], *, check: bool, cwd: Path) -> None:
        """Use this helper to emulate DVC creating the Dataset lockfile on repro."""
        assert check is True
        commands.append(command)
        if command[1:] == ["repro", "dataset"]:
            (cwd / "dvc.lock").write_text("stages:\n  dataset: {}\n")

    monkeypatch.setattr(dataset_artifact.subprocess, "run", fake_run)

    lock_path = version_dataset(dataset_root, workspace=dataset_root.parent)

    assert lock_path == dataset_root.parent / "dvc.lock"
    assert commands == [
        ["dvc", "add", "payload"],
        [
            "dvc",
            "stage",
            "add",
            "--name",
            "dataset",
            "--deps",
            "payload",
            "true",
        ],
        ["dvc", "repro", "dataset"],
    ]


def test_publish_dataset_lock_uploads_only_lockfile(tmp_path: Path) -> None:
    """Only the DVC lockfile is published as the Dataset version record."""
    lock_path = tmp_path / "dvc.lock"
    lock_path.write_text("stages:\n  dataset: {}\n")
    client = _MemoryStorageClient()

    lock_uri = publish_dataset_lock(
        client,
        bucket_name="dataset-bucket",
        artifact_prefix="datasets/example/v1",
        lock_path=lock_path,
    )

    assert lock_uri == "gs://dataset-bucket/datasets/example/v1/dvc.lock"
    blob = client.bucket("dataset-bucket").blobs["datasets/example/v1/dvc.lock"]
    assert blob.filename == str(lock_path)
    assert blob.options == {"if_generation_match": 0}


@pytest.mark.parametrize(
    ("filename", "contents"),
    [("dataset-artifact.dvc", "outs: []\n"), ("dvc.lock", None)],
)
def test_publish_dataset_lock_rejects_non_lockfile(
    tmp_path: Path, filename: str, contents: str | None
) -> None:
    """Dataset publication rejects metadata that is not an existing dvc.lock file."""
    lock_path = tmp_path / filename
    if contents is not None:
        lock_path.write_text(contents)

    with pytest.raises(ValueError, match="dvc.lock|missing"):
        publish_dataset_lock(
            _MemoryStorageClient(),
            bucket_name="dataset-bucket",
            artifact_prefix="datasets/example/v1",
            lock_path=lock_path,
        )


def test_publication_script_pushes_dataset_before_its_lockfile() -> None:
    """The Cloud Job pushes DVC-managed data before publishing its lockfile."""
    repository_root = Path(__file__).resolve().parents[1]
    script = (repository_root / "scripts/cloud/publish_dataset_artifact.sh").read_text()

    assert (
        'dvc remote add --default dataset "gs://${GCS_BUCKET}/${DATASET_ARTIFACT_PREFIX}"'
        in script
    )
    assert "version_dataset(Path(sys.argv[1]), workspace=Path(sys.argv[2]))" in script
    assert script.index("dvc push") < script.index("publish_dataset_lock")


def test_preparation_config_requires_separate_immutable_images() -> None:
    """Acquisition and DVC publication remain separate Cloud Build steps."""
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
