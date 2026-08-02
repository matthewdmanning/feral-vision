"""Publish immutable Dataset Artifacts to a versioned Cloud Storage bucket."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol


class _Blob(Protocol):
    """Use this protocol to type the Cloud Storage blob publisher dependency."""

    def upload_from_filename(self, filename: str, **kwargs: object) -> None:
        pass

    def upload_from_string(self, data: str, **kwargs: object) -> None:
        pass


class _Bucket(Protocol):
    """Use this protocol to type the Cloud Storage bucket publisher dependency."""

    def blob(self, blob_name: str) -> _Blob:
        pass


class StorageClient(Protocol):
    """Use this protocol to type the Cloud Storage client publisher dependency."""

    def bucket(self, bucket_name: str) -> _Bucket:
        pass


def load_dataset_input(input_path: Path) -> dict[str, Any]:
    """Use this function to load and validate acquisition provenance metadata."""
    try:
        data = json.loads(input_path.read_text())
    except FileNotFoundError as error:
        raise ValueError(f"Dataset input metadata is missing: {input_path}") from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Dataset input metadata is invalid JSON: {input_path}"
        ) from error

    if not isinstance(data, dict):
        raise ValueError("Dataset input metadata must be a JSON object")
    for field in ("dataset", "source", "provenance"):
        if field not in data:
            raise ValueError(f"Dataset input metadata must include {field!r}")
    if not isinstance(data["dataset"], str) or not data["dataset"].strip():
        raise ValueError(
            "Dataset input metadata field 'dataset' must be a non-empty string"
        )
    if not isinstance(data["source"], str) or not data["source"].strip():
        raise ValueError(
            "Dataset input metadata field 'source' must be a non-empty string"
        )
    if not isinstance(data["provenance"], Mapping):
        raise ValueError("Dataset input metadata field 'provenance' must be an object")
    return data


def payload_files(payload_root: Path) -> list[Path]:
    """Use this function to validate and enumerate a canonical dataset payload."""
    for directory in ("images", "annotations"):
        path = payload_root / directory
        if not path.is_dir():
            raise ValueError(
                f"Dataset payload must contain {directory}/: {payload_root}"
            )

    files = sorted(path for path in payload_root.rglob("*") if path.is_file())
    if not files:
        raise ValueError(f"Dataset payload is empty: {payload_root}")
    return files


def build_dataset_artifact(
    dataset_input: Mapping[str, Any], *, payload_file_count: int
) -> dict[str, Any]:
    """Use this function to create the manifest stored beside a Dataset Artifact."""
    return {
        "schema_version": 1,
        "kind": "Dataset Artifact",
        "dataset": dataset_input["dataset"],
        "source": dataset_input["source"],
        "provenance": dict(dataset_input["provenance"]),
        "payload": {"path": "payload", "file_count": payload_file_count},
        "dvc_tracker": {"path": "dataset-artifact.dvc"},
    }


def build_dataset_variant_artifact(
    dataset_input: Mapping[str, Any],
    *,
    payload_file_count: int,
    source_artifact_uri: str,
    augmentation_recipe: Mapping[str, Any],
) -> dict[str, Any]:
    """Use this function to record immutable raw-to-augmented Dataset Artifact lineage."""
    if not source_artifact_uri.strip():
        raise ValueError("source Dataset Artifact URI must not be empty")
    manifest = build_dataset_artifact(
        dataset_input, payload_file_count=payload_file_count
    )
    manifest["kind"] = "Dataset Variant Artifact"
    manifest["provenance"] = {
        **manifest["provenance"],
        "source_dataset_artifact": source_artifact_uri,
        "operation": "annotation-aware augmentation",
        "augmentation_recipe": dict(augmentation_recipe),
    }
    return manifest


def publish_dataset_artifact(
    client: StorageClient,
    *,
    bucket_name: str,
    artifact_prefix: str,
    payload_root: Path,
    input_path: Path,
) -> str:
    """Use this function to publish a validated payload and its manifest to Cloud Storage."""
    if not artifact_prefix.strip("/"):
        raise ValueError("Dataset artifact prefix must not be empty")

    dataset_input = load_dataset_input(input_path)
    files = payload_files(payload_root)
    prefix = artifact_prefix.strip("/")
    manifest = build_dataset_artifact(dataset_input, payload_file_count=len(files))
    _publish_payload(client.bucket(bucket_name), prefix, payload_root, files, manifest)
    return f"gs://{bucket_name}/{prefix}/payload"


def publish_dataset_variant_artifact(
    client: StorageClient,
    *,
    bucket_name: str,
    artifact_prefix: str,
    payload_root: Path,
    input_path: Path,
    source_artifact_uri: str,
    augmentation_recipe: Mapping[str, Any],
) -> str:
    """Use this function to publish an immutable augmented variant with source Artifact lineage."""
    if not artifact_prefix.strip("/"):
        raise ValueError("Dataset artifact prefix must not be empty")
    dataset_input = load_dataset_input(input_path)
    files = payload_files(payload_root)
    prefix = artifact_prefix.strip("/")
    manifest = build_dataset_variant_artifact(
        dataset_input,
        payload_file_count=len(files),
        source_artifact_uri=source_artifact_uri,
        augmentation_recipe=augmentation_recipe,
    )
    _publish_payload(client.bucket(bucket_name), prefix, payload_root, files, manifest)
    return f"gs://{bucket_name}/{prefix}/payload"


def _publish_payload(
    bucket: _Bucket,
    prefix: str,
    payload_root: Path,
    files: list[Path],
    manifest: Mapping[str, Any],
) -> None:
    """Use this function when a Dataset Artifact payload and manifest need immutable upload semantics."""
    for file_path in files:
        relative_path = file_path.relative_to(payload_root).as_posix()
        bucket.blob(f"{prefix}/payload/{relative_path}").upload_from_filename(
            str(file_path), if_generation_match=0
        )
    bucket.blob(f"{prefix}/dataset-artifact.json").upload_from_string(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        content_type="application/json",
        if_generation_match=0,
    )


def publish_dataset_tracker(
    client: StorageClient,
    *,
    bucket_name: str,
    artifact_prefix: str,
    tracker_path: Path,
) -> None:
    """Use this function to publish a generated version-aware DVC tracker."""
    if not tracker_path.is_file():
        raise ValueError(f"Dataset tracker is missing: {tracker_path}")
    prefix = artifact_prefix.strip("/")
    if not prefix:
        raise ValueError("Dataset artifact prefix must not be empty")
    client.bucket(bucket_name).blob(
        f"{prefix}/dataset-artifact.dvc"
    ).upload_from_filename(str(tracker_path), if_generation_match=0)
