"""Google Compute CLI integration contract used by cloud preflight."""

from __future__ import annotations

import json

import pytest

from scripts.cloud_preflight import PreflightRequest, get_compute_instance

_VALID_REQUEST = {
    "image": "registry/image@sha256:" + "a" * 64,
    "data_reference": "gs://dataset-bucket/datasets/animals/dvc.lock#123",
    "run_recipe": "detection",
    "runtime_overrides": (),
    "mlflow_tracking_uri": "http://localhost:5000",
    "mlflow_artifact_prefix": "gs://operations-bucket/mlflow",
    "gcp_project": "project",
    "gce_zone": "us-central1-a",
    "gce_instance": "feral-vision-trainer",
    "data_root": "/data",
    "expected_python": "3.12",
    "expected_cuda": "12",
}


# ---------------------------------------------------------------------------
# Manifest input contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_reference", "https://example.com/dvc.lock#123"),
        ("mlflow_artifact_prefix", "gs://operations-bucket"),
    ],
)
def test_preflight_request_rejects_malformed_cloud_storage_uri(
    field: str, value: str
) -> None:
    with pytest.raises(ValueError, match=field):
        PreflightRequest(**(_VALID_REQUEST | {field: value}))


@pytest.mark.parametrize(
    "data_reference",
    [
        "gs://dataset-bucket/datasets/animals/dvc.lock",
        "gs://dataset-bucket/datasets/animals/dvc.lock#latest",
    ],
)
def test_preflight_request_requires_numeric_dataset_generation(
    data_reference: str,
) -> None:
    with pytest.raises(ValueError, match="numeric #generation"):
        PreflightRequest(**(_VALID_REQUEST | {"data_reference": data_reference}))


# ---------------------------------------------------------------------------
# Compute Engine request contract
# ---------------------------------------------------------------------------


def test_get_compute_instance_calls_selected_compute_endpoint() -> None:
    """The CLI requests and returns the manifest-selected GCE instance."""
    response = {
        "kind": "compute#instance",
        "name": "feral-vision-trainer",
        "zone": "https://www.googleapis.com/compute/v1/projects/project/zones/us-central1-a",
        "status": "RUNNING",
        "serviceAccounts": [{"email": "trainer@project.iam.gserviceaccount.com"}],
    }
    commands = []

    def runner(command):
        """Record the command and return one serialized instance."""
        commands.append(command)
        return json.dumps(response)

    instance = get_compute_instance(
        "project", "us-central1-a", "feral-vision-trainer", runner=runner
    )

    assert instance == response
    assert commands == [
        (
            "gcloud",
            "compute",
            "instances",
            "describe",
            "feral-vision-trainer",
            "--project",
            "project",
            "--zone",
            "us-central1-a",
            "--format=json",
        )
    ]
