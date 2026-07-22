"""Validate Docker/GCE cloud-training prerequisites without starting training.

Run this script on the already-selected GCE instance.  It deliberately has no
provisioning, scheduling, DVC, or training behavior: its only output is durable
readiness evidence for a single immutable run identity.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
from urllib.request import urlopen
from uuid import uuid4

from hydra import compose, initialize_config_dir
from omegaconf import OmegaConf

from feral_vision.config.store import register_configs


PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DIGEST_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_IMMUTABLE_GCS = re.compile(r"^gs://[^/#]+/.+#\d+$")
_GCS_PREFIX = re.compile(r"^gs://[^/#]+(?:/.*)?$")
_RECIPE = re.compile(r"^[a-z][a-z0-9_-]*$")
CommandRunner = Callable[[Sequence[str]], str]
HttpGet = Callable[[str], int]
ComputeInstanceGetter = Callable[[str, str, str], dict[str, Any]]


@dataclass(frozen=True)
class PreflightRequest:
    """The immutable inputs and expected runtime for one cloud training run."""

    image: str
    data_reference: str
    run_recipe: str
    runtime_overrides: tuple[str, ...]
    mlflow_tracking_uri: str
    mlflow_artifact_prefix: str
    gcp_project: str
    gce_zone: str
    gce_instance: str
    data_root: str
    expected_python: str
    expected_cuda: str

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "PreflightRequest":
        """Build a request from the machine-readable manifest format."""
        required = (
            "image",
            "data_reference",
            "run_recipe",
            "mlflow_tracking_uri",
            "mlflow_artifact_prefix",
            "gcp_project",
            "gce_zone",
            "gce_instance",
            "data_root",
            "expected_python",
            "expected_cuda",
        )
        missing = [name for name in required if not isinstance(values.get(name), str)]
        if missing:
            raise ValueError(
                f"Manifest has missing or invalid fields: {', '.join(missing)}"
            )
        overrides = values.get("runtime_overrides", [])
        if not isinstance(overrides, list) or not all(
            isinstance(value, str) for value in overrides
        ):
            raise ValueError(
                "Manifest field runtime_overrides must be a list of strings"
            )
        return cls(
            **{name: values[name] for name in required},
            runtime_overrides=tuple(overrides),
        )


@dataclass(frozen=True)
class Check:
    """One recorded readiness assertion."""

    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PreflightResult:
    """Serializable pass/fail evidence that a launcher can consume later."""

    schema_version: int
    status: str
    checked_at: str
    run_identity: dict[str, Any]
    runtime_identity: dict[str, str]
    checks: tuple[Check, ...]


def _run(command: Sequence[str]) -> str:
    """Run one system command and return its stripped standard output."""
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    return completed.stdout.strip()


def _http_status(uri: str) -> int:
    """Return the MLflow endpoint's HTTP status without beginning a run."""
    with urlopen(f"{uri.rstrip('/')}/health", timeout=10) as response:  # noqa: S310
        return response.status


def get_compute_instance(
    project: str, zone: str, instance: str, *, http: Any | None = None
) -> dict[str, Any]:
    """Read the selected GCE instance through the Compute Engine API."""
    from googleapiclient.discovery import build

    if http is None:
        import google.auth
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/compute.readonly"]
        )
        http = AuthorizedHttp(credentials, httplib2.Http())

    service = build(
        "compute", "v1", http=http, cache_discovery=False, static_discovery=False
    )
    response = (
        service.instances().get(project=project, zone=zone, instance=instance).execute()
    )
    if not isinstance(response, dict):
        raise TypeError("Compute instances.get returned a non-object response")
    return response


def _command_check(name: str, command: Sequence[str], runner: CommandRunner) -> Check:
    """Record command success or its actionable failure message."""
    try:
        output = runner(command)
    except (OSError, subprocess.CalledProcessError) as exc:
        return Check(name, False, str(exc))
    return Check(name, True, output or "ok")


def _manifest_checks(request: PreflightRequest) -> list[Check]:
    """Validate immutable inputs before any cloud-facing probe runs."""
    return [
        Check(
            "immutable_image_reference",
            bool(_DIGEST_IMAGE.fullmatch(request.image)),
            request.image,
        ),
        Check(
            "immutable_data_reference",
            bool(_IMMUTABLE_GCS.fullmatch(request.data_reference)),
            request.data_reference,
        ),
        Check(
            "named_run_recipe",
            bool(_RECIPE.fullmatch(request.run_recipe)),
            request.run_recipe,
        ),
        Check(
            "mlflow_artifact_prefix",
            bool(_GCS_PREFIX.fullmatch(request.mlflow_artifact_prefix)),
            request.mlflow_artifact_prefix,
        ),
    ]


def _recipe_check(request: PreflightRequest) -> Check:
    """Compose the selected recipe and require its runtime data-root override."""
    try:
        register_configs()
        with initialize_config_dir(
            version_base=None, config_dir=str(PROJECT_ROOT / "conf")
        ):
            cfg = compose(
                config_name=f"runs/{request.run_recipe}",
                overrides=list(request.runtime_overrides),
            )
        actual_root = OmegaConf.select(cfg, "data.root")
    except Exception as exc:  # Hydra exposes several configuration exception types.
        return Check("run_recipe_composes", False, str(exc))
    if actual_root != request.data_root:
        return Check(
            "run_recipe_composes",
            False,
            f"data.root is {actual_root!r}; expected {request.data_root!r}",
        )
    return Check("run_recipe_composes", True, f"data.root={actual_root}")


def _service_account_check(account: str) -> Check:
    """Require an attached workload identity rather than a key-file credential."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return Check(
            "workload_identity_is_keyless",
            False,
            "GOOGLE_APPLICATION_CREDENTIALS is set; use the attached service account",
        )
    return Check(
        "workload_identity_is_keyless",
        account.endswith(".gserviceaccount.com"),
        account or "no active service account",
    )


def _compute_instance_check(
    request: PreflightRequest, getter: ComputeInstanceGetter
) -> tuple[Check, str]:
    """Require the manifest's GCE instance to be running with an attached identity."""
    try:
        instance = getter(request.gcp_project, request.gce_zone, request.gce_instance)
    except Exception as exc:
        return Check("compute_instance_ready", False, str(exc)), ""

    status = instance.get("status")
    accounts = instance.get("serviceAccounts", [])
    emails = [
        account.get("email")
        for account in accounts
        if isinstance(account, dict) and isinstance(account.get("email"), str)
    ]
    if status != "RUNNING":
        return (
            Check(
                "compute_instance_ready",
                False,
                f"{request.gce_instance} status is {status!r}; expected 'RUNNING'",
            ),
            "",
        )
    if not emails:
        return (
            Check(
                "compute_instance_ready",
                False,
                f"{request.gce_instance} has no attached service account",
            ),
            "",
        )
    return Check("compute_instance_ready", True, emails[0]), emails[0]


def run_preflight(
    request: PreflightRequest,
    *,
    runner: CommandRunner = _run,
    http_status: HttpGet = _http_status,
    compute_instance_getter: ComputeInstanceGetter = get_compute_instance,
) -> PreflightResult:
    """Probe a selected GCE runtime and return evidence without launching training."""
    checks = _manifest_checks(request)
    service_account = "unavailable"
    if all(check.passed for check in checks):
        artifact_probe = (
            f"{request.mlflow_artifact_prefix.rstrip('/')}/_preflight/{uuid4()}.probe"
        )
        checks.extend(
            [
                _command_check("image_pull", ("docker", "pull", request.image), runner),
                _command_check("docker_available", ("docker", "info"), runner),
                _command_check(
                    "nvidia_gpu_visible",
                    (
                        "nvidia-smi",
                        "--query-gpu=name,driver_version",
                        "--format=csv,noheader",
                    ),
                    runner,
                ),
                _command_check(
                    "ssd_mounted", ("findmnt", "--target", request.data_root), runner
                ),
                _command_check("runtime_python", ("python", "--version"), runner),
                _command_check(
                    "runtime_cuda",
                    ("python", "-c", "import torch; print(torch.version.cuda)"),
                    runner,
                ),
                _command_check(
                    "data_artifact_readable",
                    ("gcloud", "storage", "ls", request.data_reference),
                    runner,
                ),
                _command_check(
                    "mlflow_artifact_prefix_readable",
                    ("gcloud", "storage", "ls", request.mlflow_artifact_prefix),
                    runner,
                ),
                _command_check(
                    "mlflow_artifact_prefix_writable",
                    ("gcloud", "storage", "cp", "/dev/null", artifact_probe),
                    runner,
                ),
                _command_check(
                    "mlflow_artifact_probe_cleaned_up",
                    ("gcloud", "storage", "rm", artifact_probe),
                    runner,
                ),
                _recipe_check(request),
            ]
        )
        compute_check, service_account = _compute_instance_check(
            request, compute_instance_getter
        )
        checks.extend((compute_check, _service_account_check(service_account)))
        try:
            status = http_status(request.mlflow_tracking_uri)
            checks.append(
                Check("mlflow_reachable", 200 <= status < 400, f"HTTP {status}")
            )
        except OSError as exc:
            checks.append(Check("mlflow_reachable", False, str(exc)))

    command_output = {check.name: check.detail for check in checks if check.passed}
    runtime_identity = {
        "host": command_output.get("docker_available", "unavailable"),
        "gpu": command_output.get("nvidia_gpu_visible", "unavailable"),
        "service_account": service_account,
        "python": command_output.get("runtime_python", "unavailable"),
        "cuda": command_output.get("runtime_cuda", "unavailable"),
    }
    expected = {
        "python": request.expected_python,
        "cuda": request.expected_cuda,
    }
    for name, expected_value in expected.items():
        actual = runtime_identity[name]
        checks.append(
            Check(
                f"{name}_compatibility",
                actual != "unavailable" and expected_value in actual,
                f"expected {expected_value}; observed {actual}",
            )
        )
    return PreflightResult(
        schema_version=1,
        status="passed" if all(check.passed for check in checks) else "failed",
        checked_at=datetime.now(UTC).isoformat(),
        run_identity={
            "image": request.image,
            "data_reference": request.data_reference,
            "run_recipe": request.run_recipe,
            "runtime_overrides": list(request.runtime_overrides),
            "mlflow_tracking_uri": request.mlflow_tracking_uri,
            "mlflow_artifact_prefix": request.mlflow_artifact_prefix,
            "gcp_project": request.gcp_project,
            "gce_zone": request.gce_zone,
            "gce_instance": request.gce_instance,
            "preflight_id": str(uuid4()),
        },
        runtime_identity=runtime_identity,
        checks=tuple(checks),
    )


def main() -> int:
    """Write a machine-readable result and return a nonzero status on failure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    request = PreflightRequest.from_mapping(json.loads(args.manifest.read_text()))
    result = run_preflight(request)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
    print(f"Cloud preflight {result.status}: {args.output}")
    return 0 if result.status == "passed" else 1


if __name__ == "__main__":  # pragma: no cover - exercised through main().
    raise SystemExit(main())
