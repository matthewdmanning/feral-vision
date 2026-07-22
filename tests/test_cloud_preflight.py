"""Cloud-training preflight records immutable, no-GCP-testable readiness evidence."""

from __future__ import annotations

from collections.abc import Sequence

from scripts.cloud_preflight import PreflightRequest, run_preflight


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _request(**overrides: object) -> PreflightRequest:
    """Build a valid immutable cloud-training request."""
    values: dict[str, object] = {
        "image": "us-central1-docker.pkg.dev/project/repo/trainer@sha256:" + "a" * 64,
        "data_reference": "gs://training-data/feral/versioned.tar#123456789",
        "run_recipe": "baseline",
        "runtime_overrides": ["data.root=/data"],
        "mlflow_tracking_uri": "https://mlflow.example.test",
        "mlflow_artifact_prefix": "gs://mlflow-artifacts/runs",
        "data_root": "/data",
        "expected_python": "3.12",
        "expected_cuda": "12.1",
    }
    values.update(overrides)
    return PreflightRequest.from_mapping(values)


class _SuccessfulRuntime:
    """In-memory command runner representing a ready GCE runtime."""

    def __call__(self, command: Sequence[str]) -> str:
        """Return deterministic output for each supported readiness probe."""
        outputs = {
            ("docker", "info"): "Docker 27.0",
            ("nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"): "NVIDIA L4, 550.54",
            ("findmnt", "--target", "/data"): "/dev/sdb /data ext4 rw",
            ("python", "--version"): "Python 3.12.13",
            ("python", "-c", "import torch; print(torch.version.cuda)"): "12.1",
            ("gcloud", "auth", "list", "--filter=status:ACTIVE", "--format=value(account)"): "trainer@project.iam.gserviceaccount.com",
        }
        if command[:3] == ("docker", "pull", "us-central1-docker.pkg.dev/project/repo/trainer@sha256:" + "a" * 64):
            return "pulled digest"
        if command[:3] == ("gcloud", "storage", "ls"):
            return "accessible"
        if command[:3] in (("gcloud", "storage", "cp"), ("gcloud", "storage", "rm")):
            return "ok"
        return outputs[tuple(command)]


# ---------------------------------------------------------------------------
# Successful evidence
# ---------------------------------------------------------------------------


def test_preflight_records_all_required_evidence_without_gcp_calls() -> None:
    """A successful probe records the full immutable identity and runtime evidence."""
    result = run_preflight(_request(), runner=_SuccessfulRuntime(), http_status=lambda _: 200)

    assert result.status == "passed"
    assert result.run_identity["data_reference"].endswith("#123456789")
    assert result.runtime_identity["service_account"].endswith("gserviceaccount.com")
    assert {check.name for check in result.checks} >= {
        "image_pull",
        "nvidia_gpu_visible",
        "data_artifact_readable",
        "mlflow_artifact_prefix_writable",
        "workload_identity_is_keyless",
        "run_recipe_composes",
        "mlflow_reachable",
    }


# ---------------------------------------------------------------------------
# Refused prerequisites
# ---------------------------------------------------------------------------


def test_preflight_refuses_mutable_image_and_data_references() -> None:
    """Mutable tags and unversioned GCS paths cannot produce passing evidence."""
    result = run_preflight(
        _request(image="us-central1-docker.pkg.dev/project/repo/trainer:latest", data_reference="gs://training-data/feral/current"),
        runner=_SuccessfulRuntime(),
        http_status=lambda _: 200,
    )

    assert result.status == "failed"
    failed = {check.name for check in result.checks if not check.passed}
    assert {"immutable_image_reference", "immutable_data_reference"} <= failed


def test_preflight_records_failed_mlflow_probe() -> None:
    """An unreachable MLflow destination prevents a successful preflight."""
    result = run_preflight(
        _request(),
        runner=_SuccessfulRuntime(),
        http_status=lambda _: 503,
    )

    assert result.status == "failed"
    check = next(check for check in result.checks if check.name == "mlflow_reachable")
    assert not check.passed
    assert check.detail == "HTTP 503"
