"""Publish Dataset Artifacts: a plain payload and a manifest of its files."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol


class _Retention(Protocol):
    """Cloud Storage object retention configuration."""

    mode: str | None
    retain_until_time: datetime | None


class _Blob(Protocol):
    """Cloud Storage object used to publish Dataset Artifact files."""

    retention: _Retention
    generation: int | None

    def upload_from_filename(self, filename: str, **kwargs: object) -> None:
        pass

    def upload_from_string(self, data: str, **kwargs: object) -> None:
        pass


class _Bucket(Protocol):
    """Cloud Storage bucket used for Dataset Artifact publication."""

    def blob(self, blob_name: str) -> _Blob:
        pass


class StorageClient(Protocol):
    """Cloud Storage client used to publish a Dataset Artifact."""

    def bucket(self, bucket_name: str) -> _Bucket:
        pass


def validate_dataset_root(dataset_root: Path) -> None:
    """Use this function when a Dataset must have the canonical training layout."""
    for directory in ("images", "annotations"):
        if not (dataset_root / directory).is_dir():
            raise ValueError(f"Dataset must contain {directory}/: {dataset_root}")


def publish_dataset_artifact(
    client: StorageClient,
    *,
    bucket_name: str,
    artifact_prefix: str,
    payload_root: Path,
    input_path: Path,
    retention_days: int,
) -> str:
    """Use this function to publish a Dataset payload, then its manifest, to Cloud Storage."""
    uri_prefix = os.environ["GCS_URI_PREFIX"]
    prefix = _require_prefix(artifact_prefix)
    validate_dataset_root(payload_root)
    manifest = json.loads(input_path.read_text())
    if not isinstance(manifest, dict) or not manifest:
        raise ValueError(f"Dataset input must be a non-empty JSON object: {input_path}")

    if "files" in manifest:
        raise ValueError(f"Dataset input must not define files: {input_path}")
    if retention_days < 1:
        raise ValueError("Dataset retention must be at least one day")

    bucket = client.bucket(bucket_name)
    retain_until = datetime.now(UTC) + timedelta(days=retention_days)
    manifest["files"] = {}
    for file in sorted(path for path in payload_root.rglob("*") if path.is_file()):
        relative_path = file.relative_to(payload_root).as_posix()
        blob = bucket.blob(f"{prefix}/payload/{relative_path}")
        blob.retention.mode = "Unlocked"
        blob.retention.retain_until_time = retain_until
        blob.upload_from_filename(str(file), if_generation_match=0)
        with file.open("rb") as stream:
            manifest["files"][relative_path] = {
                "generation": blob.generation,
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest(),
            }
    # The manifest is written last, so a manifest proves a complete payload.
    manifest_blob = bucket.blob(f"{prefix}/dataset-artifact.json")
    manifest_blob.retention.mode = "Unlocked"
    manifest_blob.retention.retain_until_time = retain_until
    manifest_blob.upload_from_string(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        content_type="application/json",
        if_generation_match=0,
    )
    return f"{uri_prefix}{bucket_name}/{prefix}"


def _require_prefix(artifact_prefix: str) -> str:
    """Use this function to normalize a non-empty Dataset Artifact prefix."""
    prefix = artifact_prefix.strip("/")
    if not prefix:
        raise ValueError("Dataset artifact prefix must not be empty")
    return prefix
