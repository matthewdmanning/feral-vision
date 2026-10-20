#!/usr/bin/env bash
# Manual regression check; Terraform renders the real template without providers/state.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
python3 - "$here" <<'PY'
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

root = Path(sys.argv[1]).parent
spec = importlib.util.spec_from_file_location("preflight", root / "preflight/preflight.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
gcs_uri_prefix = os.environ["TF_VAR_test_gcs_uri_prefix"]
inputs = {
    "run_id": "setup-check",
    "training_image": "example.invalid/trainer@sha256:" + "a" * 64,
    "dataset_base_uri": f"{gcs_uri_prefix}test-datasets/datasets/coco/test",
    "source_annotation_generation": "123",
    "run_artifact_uri": f"{gcs_uri_prefix}test-operations/runs/setup-check",
    "local_ssd_mount_dir": "/mnt/disks/ssd",
    "dataset_host_mount_dir": "/mnt/disks/ssd/dataset",
    "dataset_container_mount_dir": "/data/dataset",
    "mlflow_tracking_uri": "sqlite:////data/mlflow.db",
    "run_config_name": "runs/detection",
}
cases = [
    ("default setup", {}, None),
    ("custom SSD mapping", {
        "local_ssd_mount_dir": "/mnt/custom",
        "dataset_host_mount_dir": "/mnt/custom/nested/data",
        "dataset_container_mount_dir": "/data/nested/data",
    }, None),
    ("SSD outside mount area", {"local_ssd_mount_dir": "/srv/ssd"}, "dataset_mount_mapping"),
    ("parent traversal", {"dataset_host_mount_dir": "/mnt/disks/ssd/../../../etc"}, "safe_dataset_host_mount_dir"),
    ("wrong container mapping", {"dataset_container_mount_dir": "/data/wrong"}, "dataset_mount_mapping"),
    ("shell substitution in tracking URL", {"mlflow_tracking_uri": "https://tracking.invalid/$(printf injected)"}, "shell_safe_tracking_uri"),
    ("broken rendered shell", {}, "startup_bash_syntax"),
]
environment = os.environ.copy()
events = subprocess.run(
    ["terraform", f"-chdir={root / 'tests'}", "test", "-filter=detection_run_unit_test.tftest.hcl", "-json", "-verbose"],
    env=environment, text=True, capture_output=True, check=True,
)
first = next(
    json.loads(line)["test_plan"] for line in events.stdout.splitlines()
    if json.loads(line).get("type") == "test_plan"
)
plan = {
    "planned_values": {
        "root_module": {"resources": [
            {"address": change["address"], "type": change["type"],
             "mode": change["mode"], "values": change["change"]["after"]}
            for change in first["resource_changes"]
            if change["change"]["after"] is not None
        ]},
        "outputs": {name: {"value": change["after"]} for name, change in first["output_changes"].items()},
    },
    "resource_changes": first["resource_changes"],
    "variables": {name: {"value": value} for name, value in (inputs | {
        "dataset_host_mount_dir": "/mnt/disks/ssd/dataset-artifact",
        "dataset_container_mount_dir": "/data/dataset-artifact",
    }).items()},
}
module._plan_checks(plan, module.Reporter())
trainer = next(resource for resource in plan["planned_values"]["root_module"]["resources"] if resource["mode"] == "managed")
trainer["values"]["metadata_startup_script"] += '\nprintf "unterminated\n'
reporter = module.Reporter()
try:
    module._plan_checks(plan, reporter)
except module.PreflightFailure:
    assert reporter.results[-1].name == "startup_bash_syntax"
else:
    raise AssertionError("The deployment gate accepted a broken rendered script")
print("PASS: actual mocked plan reaches the startup gate and broken Bash blocks deployment")

with tempfile.TemporaryDirectory(prefix="feral-download-guard-") as directory:
    temporary = Path(directory)
    engine = temporary / "docker"
    engine.write_text("""#!/bin/sh
printf '%s\n' "$*" >> "$DOCKER_CALL_LOG"
case "$1" in
version) exit 0;;
image) test "$CACHE_PRESENT" = 1 || exit 1; printf '%s\n' '[{"Os":"linux","Architecture":"amd64","Config":{"Entrypoint":["bash","/workspace/feral-vision/scripts/runs/container_train.sh"]}}]';;
info) case "$3" in '{{.MemTotal}}') printf '%s\n' "$DOCKER_MEMORY";; *) echo 4;; esac;;
run) cat >/dev/null;;
*) exit 99;;
esac
""")
    engine.chmod(0o700)
    log = temporary / "calls"
    for cached in (False, True):
        log.write_text("")
        reporter = module.Reporter()
        with patch.object(module.shutil, "which", return_value=str(engine)), patch.dict(os.environ, {
            "CACHE_PRESENT": str(int(cached)), "DOCKER_CALL_LOG": str(log),
        }):
            try:
                module._training_setup_checks(inputs["training_image"], reporter)
            except module.PreflightFailure:
                assert not cached and reporter.results[-1].name == "no_implicit_image_download"
            else:
                assert cached, "A missing image did not block deployment"
        calls = log.read_text().splitlines()
        assert not any(call.startswith(("pull ", "run ")) for call in calls), calls
        print(f"PASS: cached={cached}; no pulls and no container runs")

with tempfile.TemporaryDirectory(prefix="feral-startup-check-") as work:
    for label, changes, expected in cases:
        values = inputs | changes
        expression = "jsonencode(templatefile(" + json.dumps(str(root / "runs/detection/templates/trainer_startup.sh.tftpl")) + "," + json.dumps(values) + "))"
        rendered = subprocess.run(
            ["terraform", f"-chdir={work}", "console", "-no-color"],
            input=expression + "\n", text=True, capture_output=True, check=True,
        )
        script = json.loads(json.loads(rendered.stdout))
        if label == "broken rendered shell":
            script += '\nprintf "unterminated\n'
        reporter = module.Reporter()
        try:
            module._startup_checks(script, values, reporter)
        except module.PreflightFailure:
            assert expected is not None and reporter.results[-1].name == expected, label
        else:
            assert expected is None, f"Broken setup was accepted: {label}"
        print(f"PASS: {label}")
PY
