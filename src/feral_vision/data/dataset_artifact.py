"""Record Dataset folders with DVC and publish their lockfiles."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol


class _Blob(Protocol):
    """Cloud Storage object used to publish a Dataset lockfile."""

    def upload_from_filename(self, filename: str, **kwargs: object) -> None:
        pass


class _Bucket(Protocol):
    """Cloud Storage bucket used for Dataset lockfile publication."""

    def blob(self, blob_name: str) -> _Blob:
        pass


class StorageClient(Protocol):
    """Cloud Storage client used to publish a Dataset lockfile."""

    def bucket(self, bucket_name: str) -> _Bucket:
        pass


def validate_dataset_root(dataset_root: Path) -> None:
    """Use this function when a DVC Dataset must have the canonical training layout."""
    for directory in ("images", "annotations"):
        if not (dataset_root / directory).is_dir():
            raise ValueError(f"Dataset must contain {directory}/: {dataset_root}")


def version_dataset(dataset_root: Path, *, workspace: Path) -> Path:
    """Use this function to record one acquired Dataset folder in a DVC lockfile."""
    validate_dataset_root(dataset_root)
    try:
        dataset_path = dataset_root.resolve().relative_to(workspace.resolve())
    except ValueError as error:
        raise ValueError("Dataset must be inside its DVC workspace") from error

    dataset_name = dataset_path.as_posix()
    _run_dvc("add", dataset_name, workspace=workspace)
    _run_dvc(
        "stage",
        "add",
        "--name",
        "dataset",
        "--deps",
        dataset_name,
        "true",
        workspace=workspace,
    )
    _run_dvc("repro", "dataset", workspace=workspace)
    return require_dataset_lock(workspace / "dvc.lock")


def require_dataset_lock(lock_path: Path) -> Path:
    """Use this function when publication requires the DVC lockfile for a Dataset."""
    if lock_path.name != "dvc.lock":
        raise ValueError("Dataset version record must be named dvc.lock")
    if not lock_path.is_file():
        raise ValueError(f"Dataset lockfile is missing: {lock_path}")
    return lock_path


def publish_dataset_lock(
    client: StorageClient,
    *,
    bucket_name: str,
    artifact_prefix: str,
    lock_path: Path,
) -> str:
    """Use this function to publish one DVC Dataset lockfile to Cloud Storage."""
    if not artifact_prefix.strip("/"):
        raise ValueError("Dataset artifact prefix must not be empty")
    lockfile = require_dataset_lock(lock_path)
    prefix = artifact_prefix.strip("/")
    client.bucket(bucket_name).blob(f"{prefix}/dvc.lock").upload_from_filename(
        str(lockfile), if_generation_match=0
    )
    return f"gs://{bucket_name}/{prefix}/dvc.lock"


def _run_dvc(*arguments: str, workspace: Path) -> None:
    """Use this function to run a DVC command in the workspace that owns a Dataset."""
    subprocess.run(["dvc", *arguments], check=True, cwd=workspace)
