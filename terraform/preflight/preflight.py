#!/usr/bin/env python3
"""Fail-fast preflight for the canonical single-VM GPU training deployment.

This command never applies Terraform. It validates the repository contract,
Terraform configuration and saved plan, required GCP resources, and the exact
published Dataset Artifact manifest. A passing run writes a hash-pinned
deployment-manifest.json consumed by scripts/runs/detection.sh.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4


CLOUD_PLATFORM_SCOPES = {
    "cloud-platform",
    "https://www.googleapis.com/auth/cloud-platform",
}
TRAINING_IMAGE_PATTERN = re.compile(
    r"^[a-z0-9][a-z0-9._/@:-]*@sha256:[0-9a-f]{64}$"
)
BOOT_IMAGE_PATTERN = re.compile(r"(?:^|/)projects/([^/]+)/global/images/([^/]+)$")
CANONICAL_RUN_RECIPE = "detection.yaml"
CANONICAL_BOOT_FAMILY = "pytorch-2-9-cu129-ubuntu-2204-nvidia-580"


@dataclass
class CheckResult:
    checkpoint: str
    name: str
    status: str
    detail: str
    duration_seconds: float = 0.0
    command: list[str] | None = None


class PreflightFailure(RuntimeError):
    """A blocking deployment-preflight failure."""


class Reporter:
    """Record ordered checkpoints to stdout and durable reports."""

    def __init__(self) -> None:
        self.started_at = datetime.now(UTC)
        self.results: list[CheckResult] = []

    @staticmethod
    def _redact_command(command: Iterable[str]) -> list[str]:
        parts = list(command)
        redacted: list[str] = []
        redact_next_var = False
        for part in parts:
            if redact_next_var:
                redacted.append(f"{part.split('=', 1)[0]}=<redacted>")
                redact_next_var = False
                continue
            redacted.append(part)
            redact_next_var = part == "-var"
        return redacted

    def record(
        self,
        checkpoint: str,
        name: str,
        status: str,
        detail: str,
        *,
        duration: float = 0.0,
        command: Iterable[str] | None = None,
    ) -> None:
        result = CheckResult(
            checkpoint=checkpoint,
            name=name,
            status=status,
            detail=detail,
            duration_seconds=round(duration, 3),
            command=self._redact_command(command) if command else None,
        )
        self.results.append(result)
        stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{stamp}] [{checkpoint}] {status:5} {name}: {detail}", flush=True)

    def assertion(
        self, checkpoint: str, name: str, condition: bool, detail: str
    ) -> None:
        self.record(checkpoint, name, "PASS" if condition else "FAIL", detail)
        if not condition:
            raise PreflightFailure(f"{checkpoint}/{name} failed: {detail}")

    def warning(self, checkpoint: str, name: str, detail: str) -> None:
        self.record(checkpoint, name, "WARN", detail)

    def command(
        self,
        checkpoint: str,
        name: str,
        command: list[str],
        *,
        cwd: Path | None = None,
        required: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        start = time.monotonic()
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        duration = time.monotonic() - start
        output = (completed.stdout or completed.stderr).strip()
        detail = output[-1200:] if output else f"exit={completed.returncode}"
        if completed.returncode == 0:
            self.record(
                checkpoint,
                name,
                "PASS",
                detail or "ok",
                duration=duration,
                command=command,
            )
            return completed

        status = "FAIL" if required else "WARN"
        self.record(
            checkpoint,
            name,
            status,
            detail,
            duration=duration,
            command=command,
        )
        if required:
            raise PreflightFailure(f"{checkpoint}/{name} failed")
        return completed

    def write(self, report_dir: Path, metadata: dict[str, Any]) -> None:
        report_dir.mkdir(parents=True, exist_ok=True)
        failed = any(result.status == "FAIL" for result in self.results)
        payload = {
            "schema_version": 1,
            "status": "failed" if failed else "passed",
            "started_at": self.started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "metadata": metadata,
            "results": [asdict(result) for result in self.results],
        }
        (report_dir / "preflight-report.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n"
        )
        lines = [
            f"Terraform GPU deployment preflight: {payload['status'].upper()}",
            f"Started:  {payload['started_at']}",
            f"Finished: {payload['finished_at']}",
            "",
        ]
        lines.extend(
            f"[{result.checkpoint}] {result.status:5} "
            f"{result.name}: {result.detail}"
            for result in self.results
        )
        (report_dir / "preflight-report.txt").write_text("\n".join(lines) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_contract(repository_root: Path, reporter: Reporter) -> None:
    checkpoint = "REPOSITORY_CONTRACT"

    run_recipes = sorted((repository_root / "conf" / "runs").glob("*.yaml"))
    reporter.assertion(
        checkpoint,
        "single_run_recipe",
        [path.name for path in run_recipes] == [CANONICAL_RUN_RECIPE],
        f"run recipes={[path.name for path in run_recipes]}",
    )

    training_dockerfiles = sorted(repository_root.glob("deploy/**/Dockerfile.gcp"))
    canonical_dockerfile = repository_root / "deploy" / "Dockerfile.gcp"
    reporter.assertion(
        checkpoint,
        "single_training_dockerfile",
        training_dockerfiles == [canonical_dockerfile],
        "training Dockerfiles="
        f"{[str(path.relative_to(repository_root)) for path in training_dockerfiles]}",
    )

    entrypoints = sorted(
        (repository_root / "scripts" / "runs").glob("*container_train*.sh")
    )
    canonical_entrypoint = repository_root / "scripts" / "runs" / "container_train.sh"
    reporter.assertion(
        checkpoint,
        "single_container_entrypoint",
        entrypoints == [canonical_entrypoint],
        "container entrypoints="
        f"{[str(path.relative_to(repository_root)) for path in entrypoints]}",
    )

    startup_template = (
        repository_root
        / "terraform"
        / "runs"
        / "detection"
        / "templates"
        / "trainer_startup.sh.tftpl"
    )
    reporter.assertion(
        checkpoint,
        "startup_template_exists",
        startup_template.is_file(),
        str(startup_template),
    )

    runtime = "\n".join(
        (startup_template.read_text(), canonical_entrypoint.read_text())
    ).lower()
    forbidden = [
        token
        for token in ("dvc init", "dvc add", "dvc repro", "dvc.lock")
        if token in runtime
    ]
    reporter.assertion(
        checkpoint,
        "no_gpu_runtime_dvc",
        not forbidden,
        f"forbidden runtime tokens={forbidden}"
        if forbidden
        else "no DVC runtime commands or lockfile gates",
    )
    reporter.assertion(
        checkpoint,
        "dataset_manifest_is_runtime_contract",
        "dataset-artifact.json" in runtime,
        "dataset-artifact.json must be staged and verified before training",
    )


def _root_resources(module: dict[str, Any]) -> list[dict[str, Any]]:
    resources = list(module.get("resources", []))
    for child in module.get("child_modules", []):
        resources.extend(_root_resources(child))
    return resources


def _output(plan: dict[str, Any], name: str) -> Any:
    value = (
        plan.get("planned_values", {})
        .get("outputs", {})
        .get(name, {})
        .get("value")
    )
    if value is None:
        raise PreflightFailure(f"Terraform plan did not produce required output {name!r}")
    return value


def _plan_contract(plan: dict[str, Any], reporter: Reporter) -> dict[str, Any]:
    checkpoint = "PLAN_CONTRACT"
    root = plan.get("planned_values", {}).get("root_module", {})
    resources = _root_resources(root)
    managed = [resource for resource in resources if resource.get("mode") == "managed"]

    reporter.assertion(
        checkpoint,
        "single_managed_resource",
        len(managed) == 1 and managed[0].get("type") == "google_compute_instance",
        f"managed resources={[(r.get('address'), r.get('type')) for r in managed]}",
    )
    trainer = managed[0]
    values = trainer.get("values", {})
    reporter.assertion(
        checkpoint,
        "trainer_address",
        trainer.get("address") == "google_compute_instance.trainer",
        f"address={trainer.get('address')}",
    )

    unsafe: list[tuple[str | None, list[str]]] = []
    for change in plan.get("resource_changes", []):
        if change.get("mode") != "managed":
            continue
        actions = change.get("change", {}).get("actions", [])
        if actions not in (["create"], ["no-op"]):
            unsafe.append((change.get("address"), actions))
    reporter.assertion(
        checkpoint,
        "no_update_replace_or_destroy",
        not unsafe,
        f"unsafe changes={unsafe}" if unsafe else "only create/no-op actions",
    )

    name = values.get("name", "")
    reporter.assertion(
        checkpoint,
        "valid_vm_name_length",
        isinstance(name, str) and 1 <= len(name) <= 63,
        f"name={name!r}, length={len(name) if isinstance(name, str) else 'unknown'}",
    )
    reporter.assertion(
        checkpoint,
        "fixed_machine_type",
        values.get("machine_type") == "n1-standard-4",
        f"machine_type={values.get('machine_type')!r}",
    )

    accelerators = values.get("guest_accelerator", [])
    reporter.assertion(
        checkpoint,
        "single_t4_gpu",
        (
            len(accelerators) == 1
            and accelerators[0].get("type") == "nvidia-tesla-t4"
            and accelerators[0].get("count") == 1
        ),
        f"guest_accelerator={accelerators}",
    )

    scratch = values.get("scratch_disk", [])
    reporter.assertion(
        checkpoint,
        "single_nvme_local_ssd",
        len(scratch) == 1 and scratch[0].get("interface") == "NVME",
        f"scratch_disk={scratch}",
    )

    scheduling = values.get("scheduling", [{}])[0]
    reporter.assertion(
        checkpoint,
        "flex_start_lifecycle",
        (
            scheduling.get("provisioning_model") == "FLEX_START"
            and scheduling.get("on_host_maintenance") == "TERMINATE"
            and scheduling.get("automatic_restart") is False
            and scheduling.get("instance_termination_action") == "DELETE"
        ),
        f"scheduling={scheduling}",
    )

    interfaces = values.get("network_interface", [])
    reporter.assertion(
        checkpoint,
        "external_ipv4_configured",
        len(interfaces) == 1 and len(interfaces[0].get("access_config", [])) == 1,
        f"network_interface_count={len(interfaces)}",
    )

    service_accounts = values.get("service_account", [])
    scopes = service_accounts[0].get("scopes", []) if len(service_accounts) == 1 else []
    reporter.assertion(
        checkpoint,
        "service_account_scope",
        len(service_accounts) == 1 and bool(CLOUD_PLATFORM_SCOPES.intersection(scopes)),
        f"service_account={service_accounts}",
    )

    metadata = values.get("metadata", {})
    reporter.assertion(
        checkpoint,
        "no_first_boot_driver_install",
        "install-nvidia-driver" not in metadata,
        f"metadata_keys={sorted(metadata) if isinstance(metadata, dict) else metadata}",
    )

    forbidden_types = {
        "google_compute_subnetwork",
        "google_compute_router",
        "google_compute_router_nat",
        "google_compute_firewall",
        "google_project_iam_binding",
        "google_project_iam_member",
        "google_storage_bucket_iam_binding",
        "google_storage_bucket_iam_member",
    }
    forbidden_resources = [
        resource.get("address")
        for resource in managed
        if resource.get("type") in forbidden_types
    ]
    reporter.assertion(
        checkpoint,
        "no_shared_network_or_iam_ownership",
        not forbidden_resources,
        f"forbidden managed resources={forbidden_resources}"
        if forbidden_resources
        else "none",
    )

    startup_script = values.get("metadata_startup_script", "")
    reporter.assertion(
        checkpoint,
        "canonical_startup_contract",
        (
            isinstance(startup_script, str)
            and "runs/detection" in startup_script
            and "dataset-artifact.json" in startup_script
            and "dvc init" not in startup_script.lower()
            and "dvc repro" not in startup_script.lower()
            and "dvc.lock" not in startup_script.lower()
        ),
        "rendered startup must use runs/detection + dataset-artifact.json and contain no GPU-side DVC",
    )

    training_image = str(_output(plan, "training_image"))
    reporter.assertion(
        checkpoint,
        "digest_pinned_training_image",
        bool(TRAINING_IMAGE_PATTERN.fullmatch(training_image)),
        training_image,
    )

    boot_image = str(_output(plan, "boot_image"))
    boot_match = BOOT_IMAGE_PATTERN.search(boot_image)
    reporter.assertion(
        checkpoint,
        "concrete_boot_image",
        boot_match is not None
        and "/global/images/family/" not in boot_image
        and CANONICAL_BOOT_FAMILY in boot_image,
        boot_image,
    )

    return {
        "run_id": _output(plan, "run_id"),
        "project_id": _output(plan, "project_id"),
        "zone": _output(plan, "trainer_zone"),
        "network_name": _output(plan, "network_name"),
        "service_account": _output(plan, "trainer_service_account"),
        "machine_type": _output(plan, "trainer_machine_type"),
        "gpu_type": _output(plan, "trainer_gpu_type"),
        "boot_image": boot_image,
        "training_image": training_image,
        "dataset_uri": _output(plan, "dataset_artifact_uri"),
        "annotation_generation": str(_output(plan, "source_annotation_generation")),
        "run_artifact_uri": _output(plan, "run_artifact_uri"),
        "vm_name": _output(plan, "trainer_instance_name"),
    }


def _gcloud_json(
    reporter: Reporter,
    checkpoint: str,
    name: str,
    command: list[str],
) -> dict[str, Any]:
    completed = reporter.command(checkpoint, name, command)
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise PreflightFailure(f"{name} returned invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PreflightFailure(f"{name} returned non-object JSON")
    return value


def _quota_available(quotas: list[dict[str, Any]], metric: str) -> float | None:
    quota = next((item for item in quotas if item.get("metric") == metric), None)
    if not quota:
        return None
    return float(quota.get("limit", 0)) - float(quota.get("usage", 0))


def _temporary_quota(
    quotas: list[dict[str, Any]],
    standard_metric: str,
    preemptible_metric: str,
) -> tuple[str, float] | None:
    preemptible = next(
        (item for item in quotas if item.get("metric") == preemptible_metric),
        None,
    )
    if preemptible and float(preemptible.get("limit", 0)) > 0:
        return (
            preemptible_metric,
            float(preemptible.get("limit", 0)) - float(preemptible.get("usage", 0)),
        )
    standard = _quota_available(quotas, standard_metric)
    if standard is None:
        return None
    return standard_metric, standard


def _cloud_checks(
    facts: dict[str, Any],
    reporter: Reporter,
    report_dir: Path,
) -> None:
    checkpoint = "GCP_PREREQUISITES"
    project = str(facts["project_id"])
    zone = str(facts["zone"])

    reporter.command(
        checkpoint,
        "project_access",
        ["gcloud", "projects", "describe", project, "--format=json"],
    )
    zone_info = _gcloud_json(
        reporter,
        checkpoint,
        "zone_available",
        [
            "gcloud",
            "compute",
            "zones",
            "describe",
            zone,
            "--project",
            project,
            "--format=json",
        ],
    )
    reporter.assertion(
        checkpoint,
        "zone_status_up",
        zone_info.get("status") == "UP",
        f"zone status={zone_info.get('status')!r}",
    )
    region = str(zone_info.get("region", "")).rstrip("/").split("/")[-1]

    reporter.command(
        checkpoint,
        "machine_type_available",
        [
            "gcloud",
            "compute",
            "machine-types",
            "describe",
            str(facts["machine_type"]),
            "--zone",
            zone,
            "--project",
            project,
            "--format=json",
        ],
    )
    reporter.command(
        checkpoint,
        "gpu_type_available",
        [
            "gcloud",
            "compute",
            "accelerator-types",
            "describe",
            str(facts["gpu_type"]),
            "--zone",
            zone,
            "--project",
            project,
            "--format=json",
        ],
    )

    network = _gcloud_json(
        reporter,
        checkpoint,
        "network_exists",
        [
            "gcloud",
            "compute",
            "networks",
            "describe",
            str(facts["network_name"]),
            "--project",
            project,
            "--format=json",
        ],
    )
    reporter.assertion(
        checkpoint,
        "network_is_auto_mode",
        network.get("autoCreateSubnetworks") is True,
        f"autoCreateSubnetworks={network.get('autoCreateSubnetworks')!r}",
    )

    reporter.command(
        checkpoint,
        "service_account_exists",
        [
            "gcloud",
            "iam",
            "service-accounts",
            "describe",
            str(facts["service_account"]),
            "--project",
            project,
            "--format=json",
        ],
    )

    boot_match = BOOT_IMAGE_PATTERN.search(str(facts["boot_image"]))
    if boot_match is None:
        raise PreflightFailure(
            "resolved boot image is not a concrete Compute Engine image: "
            f"{facts['boot_image']}"
        )
    image_project, image_name = boot_match.groups()
    image_info = _gcloud_json(
        reporter,
        checkpoint,
        "boot_image_exists",
        [
            "gcloud",
            "compute",
            "images",
            "describe",
            image_name,
            "--project",
            image_project,
            "--format=json",
        ],
    )
    reporter.assertion(
        checkpoint,
        "boot_image_family",
        image_info.get("family") == CANONICAL_BOOT_FAMILY,
        f"family={image_info.get('family')!r}",
    )

    reporter.command(
        checkpoint,
        "training_image_digest_exists",
        [
            "gcloud",
            "artifacts",
            "docker",
            "images",
            "describe",
            str(facts["training_image"]),
            "--format=json",
        ],
    )

    dataset_uri = str(facts["dataset_uri"]).rstrip("/")
    manifest_uri = f"{dataset_uri}/dataset-artifact.json"
    manifest_path = report_dir / "dataset-artifact.preflight.json"
    reporter.command(
        checkpoint,
        "dataset_manifest_download",
        ["gcloud", "storage", "cp", manifest_uri, str(manifest_path), "--quiet"],
    )
    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreflightFailure(
            f"dataset-artifact.json is not valid UTF-8 JSON: {exc}"
        ) from exc
    reporter.assertion(
        checkpoint,
        "dataset_manifest_valid_json_object",
        isinstance(manifest, dict) and bool(manifest),
        f"top-level keys={sorted(manifest) if isinstance(manifest, dict) else 'not-an-object'}",
    )
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    facts["dataset_artifact_sha256"] = manifest_sha256
    reporter.record(checkpoint, "dataset_manifest_sha256", "PASS", manifest_sha256)

    reporter.command(
        checkpoint,
        "dataset_images_prefix_exists",
        ["gcloud", "storage", "ls", f"{dataset_uri}/payload/images"],
    )
    annotation_uri = (
        f"{dataset_uri}/payload/annotations/instances.json"
        f"#{facts['annotation_generation']}"
    )
    reporter.command(
        checkpoint,
        "pinned_annotation_generation_exists",
        [
            "gcloud",
            "storage",
            "objects",
            "describe",
            annotation_uri,
            "--format=json",
        ],
    )

    region_info = _gcloud_json(
        reporter,
        checkpoint,
        "regional_quota_snapshot",
        [
            "gcloud",
            "compute",
            "regions",
            "describe",
            region,
            "--project",
            project,
            "--format=json",
        ],
    )
    quotas = region_info.get("quotas", [])
    if not isinstance(quotas, list):
        raise PreflightFailure("regional quota response did not contain a quota list")

    cpu_quota = _temporary_quota(quotas, "CPUS", "PREEMPTIBLE_CPUS")
    if cpu_quota:
        metric, available = cpu_quota
        reporter.assertion(
            checkpoint,
            "cpu_quota_at_least_4",
            available >= 4,
            f"{metric} available={available:g}",
        )
    else:
        reporter.warning(
            checkpoint,
            "cpu_quota_at_least_4",
            "Neither standard nor preemptible CPU quota metric was returned",
        )

    t4_quota = _temporary_quota(
        quotas,
        "NVIDIA_T4_GPUS",
        "PREEMPTIBLE_NVIDIA_T4_GPUS",
    )
    if t4_quota:
        metric, available = t4_quota
        reporter.assertion(
            checkpoint,
            "t4_quota_at_least_1",
            available >= 1,
            f"{metric} available={available:g}",
        )
    else:
        reporter.warning(
            checkpoint,
            "t4_quota_at_least_1",
            "Neither standard nor preemptible T4 quota metric was returned; zonal accelerator availability was verified but allocation can still fail",
        )

    external_ips = _quota_available(quotas, "IN_USE_ADDRESSES")
    if external_ips is not None:
        reporter.assertion(
            checkpoint,
            "external_ip_quota_at_least_1",
            external_ips >= 1,
            f"IN_USE_ADDRESSES available={external_ips:g}",
        )
    else:
        reporter.warning(
            checkpoint,
            "external_ip_quota_at_least_1",
            "IN_USE_ADDRESSES quota metric not returned",
        )

    local_ssd = _temporary_quota(
        quotas,
        "LOCAL_SSD_TOTAL_GB_PER_VM_FAMILY",
        "PREEMPTIBLE_LOCAL_SSD_GB",
    )
    if local_ssd:
        metric, available = local_ssd
        reporter.assertion(
            checkpoint,
            "local_ssd_quota_at_least_375_gb",
            available >= 375,
            f"{metric} available={available:g} GB",
        )
    else:
        reporter.warning(
            checkpoint,
            "local_ssd_quota_at_least_375_gb",
            "Local SSD quota metric not returned by the regional API; some Local SSD quota is exposed through Cloud Quotas instead",
        )


def _artifact_write_probe(facts: dict[str, Any], reporter: Reporter) -> None:
    checkpoint = "ARTIFACT_WRITE_PROBE"
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".txt") as handle:
        handle.write("feral-vision terraform preflight probe\n")
        local_path = Path(handle.name)
    remote = (
        f"{str(facts['run_artifact_uri']).rstrip('/')}/_preflight/"
        f"write-probe-{uuid4().hex}.txt"
    )
    try:
        reporter.command(
            checkpoint,
            "artifact_prefix_write",
            ["gcloud", "storage", "cp", str(local_path), remote],
        )
        reporter.command(
            checkpoint,
            "artifact_prefix_cleanup",
            ["gcloud", "storage", "rm", remote],
        )
    finally:
        local_path.unlink(missing_ok=True)


def _write_deployment_manifest(
    report_dir: Path,
    plan_path: Path,
    facts: dict[str, Any],
    reporter: Reporter,
) -> None:
    checkpoint = "DEPLOYMENT_MANIFEST"
    plan_sha256 = _sha256(plan_path)
    manifest = {
        "schema_version": 1,
        "status": "ready-for-apply",
        "created_at": datetime.now(UTC).isoformat(),
        "terraform_plan": str(plan_path.resolve()),
        "terraform_plan_sha256": plan_sha256,
        **facts,
    }
    manifest_path = report_dir / "deployment-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    reporter.record(
        checkpoint,
        "saved_plan_manifest",
        "PASS",
        f"{manifest_path} plan_sha256={plan_sha256}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "runs" / "detection",
    )
    parser.add_argument("--var-file", type=Path)
    parser.add_argument("--var", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=(
            Path(__file__).resolve().parent
            / "reports"
            / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        ),
    )
    parser.add_argument(
        "--skip-write-probe",
        action="store_true",
        help="Skip the reversible artifact-prefix write/delete probe.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    reporter = Reporter()
    report_dir = args.report_dir.resolve()
    repository_root = Path(__file__).resolve().parents[2]
    metadata: dict[str, Any] = {
        "terraform_dir": str(args.terraform_dir.resolve()),
        "report_dir": str(report_dir),
        "var_file": str(args.var_file.resolve()) if args.var_file else None,
        "cli_variable_names": [value.split("=", 1)[0] for value in args.var],
    }

    try:
        checkpoint = "LOCAL_TOOLING"
        for tool in ("terraform", "gcloud"):
            location = shutil.which(tool)
            reporter.assertion(
                checkpoint,
                f"{tool}_installed",
                location is not None,
                f"{tool}={location}",
            )
        reporter.command(checkpoint, "terraform_version", ["terraform", "version"])
        reporter.command(checkpoint, "gcloud_version", ["gcloud", "version"])
        auth = reporter.command(
            checkpoint,
            "gcloud_active_account",
            [
                "gcloud",
                "auth",
                "list",
                "--filter=status:ACTIVE",
                "--format=value(account)",
            ],
        )
        reporter.assertion(
            checkpoint,
            "gcloud_account_nonempty",
            bool(auth.stdout.strip()),
            auth.stdout.strip() or "no active account",
        )

        _repository_contract(repository_root, reporter)

        terraform_dir = args.terraform_dir.resolve()
        reporter.assertion(
            "STATIC_TERRAFORM",
            "terraform_dir_exists",
            terraform_dir.is_dir(),
            str(terraform_dir),
        )
        reporter.command(
            "STATIC_TERRAFORM",
            "fmt_check",
            ["terraform", f"-chdir={terraform_dir}", "fmt", "-check", "-recursive"],
        )
        reporter.command(
            "STATIC_TERRAFORM",
            "init",
            ["terraform", f"-chdir={terraform_dir}", "init", "-input=false"],
        )
        reporter.command(
            "STATIC_TERRAFORM",
            "validate",
            ["terraform", f"-chdir={terraform_dir}", "validate"],
        )

        report_dir.mkdir(parents=True, exist_ok=True)
        plan_path = report_dir / "deployment.tfplan"
        plan_json_path = report_dir / "deployment-plan.json"
        plan_cmd = [
            "terraform",
            f"-chdir={terraform_dir}",
            "plan",
            "-input=false",
            "-lock-timeout=30s",
            f"-out={plan_path}",
        ]
        if args.var_file:
            plan_cmd.append(f"-var-file={args.var_file.resolve()}")
        for value in args.var:
            plan_cmd.extend(["-var", value])
        reporter.command("TERRAFORM_PLAN", "saved_plan", plan_cmd)
        shown = reporter.command(
            "TERRAFORM_PLAN",
            "plan_json",
            [
                "terraform",
                f"-chdir={terraform_dir}",
                "show",
                "-json",
                str(plan_path),
            ],
        )
        plan_json_path.write_text(shown.stdout)
        plan = json.loads(shown.stdout)
        facts = _plan_contract(plan, reporter)
        metadata.update(facts)

        _cloud_checks(facts, reporter, report_dir)
        metadata.update(facts)

        if args.skip_write_probe:
            reporter.warning(
                "ARTIFACT_WRITE_PROBE",
                "artifact_prefix_write",
                "skipped by operator",
            )
        else:
            _artifact_write_probe(facts, reporter)

        _write_deployment_manifest(report_dir, plan_path, facts, reporter)
        reporter.record(
            "SUMMARY",
            "deployment_preflight",
            "PASS",
            "all blocking checks passed; apply only the saved plan named in deployment-manifest.json",
        )
        return_code = 0
    except (PreflightFailure, json.JSONDecodeError, OSError) as exc:
        reporter.record("SUMMARY", "deployment_preflight", "FAIL", str(exc))
        return_code = 1
    finally:
        reporter.write(report_dir, metadata)
        print(f"Reports: {report_dir}", flush=True)

    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
