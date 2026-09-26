#!/usr/bin/env bash
set -euo pipefail

readonly terraform_root="terraform/runs/detection"

usage() {
  cat <<'EOF'
Usage:
  scripts/runs/detection.sh --manifest terraform/preflight/reports/<timestamp>/deployment-manifest.json

Applies only the exact saved Terraform plan that passed deployment preflight,
then captures VM startup logs and terminal training evidence.
EOF
}

manifest_path=""
while (( "$#" )); do
  case "$1" in
    --manifest) manifest_path="${2:?--manifest requires a path}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [ -z "$manifest_path" ] || [ ! -f "$manifest_path" ]; then
  echo "A valid --manifest from terraform/preflight/preflight.py is required." >&2
  exit 2
fi

manifest_path="$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve())' "$manifest_path")"
readonly manifest_path
readonly evidence_dir="$(dirname "$manifest_path")"

checkpoint() {
  printf '[gpu-run] %s %-22s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"
}

read_manifest() {
  python3 - "$manifest_path" "$1" <<'PY'
import json
import sys

value = json.loads(open(sys.argv[1], encoding="utf-8").read())[sys.argv[2]]
if value is None or value == "":
    raise SystemExit(f"manifest field {sys.argv[2]!r} is empty")
print(value)
PY
}

read_output() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

value = json.loads(open(sys.argv[1], encoding="utf-8").read())[sys.argv[2]]["value"]
if value is None or value == "":
    raise SystemExit(f"terraform output {sys.argv[2]!r} is empty")
print(value)
PY
}

read_evidence() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

value = json.loads(open(sys.argv[1], encoding="utf-8").read()).get(sys.argv[2], "")
if value is None:
    value = ""
print(value)
PY
}

checkpoint "MANIFEST" "validating preflight artifact"
test "$(read_manifest status)" = "ready-for-apply"
readonly plan_path="$(read_manifest terraform_plan)"
readonly expected_plan_sha256="$(read_manifest terraform_plan_sha256)"
readonly expected_run_id="$(read_manifest run_id)"
readonly expected_dataset_sha256="$(read_manifest dataset_artifact_sha256)"
readonly expected_training_image="$(read_manifest training_image)"
test -f "$plan_path"
actual_plan_sha256="$(sha256sum "$plan_path" | awk '{print $1}')"
if [ "$actual_plan_sha256" != "$expected_plan_sha256" ]; then
  echo "Saved Terraform plan changed after preflight." >&2
  echo "expected=$expected_plan_sha256 actual=$actual_plan_sha256" >&2
  exit 1
fi
checkpoint "MANIFEST" "PASS plan_sha256=$actual_plan_sha256"

checkpoint "TERRAFORM_APPLY" "applying reviewed plan"
terraform -chdir="$terraform_root" apply -input=false "$plan_path"
readonly output_path="$evidence_dir/terraform-output.json"
terraform -chdir="$terraform_root" output -json >"$output_path"
checkpoint "TERRAFORM_APPLY" "PASS outputs=$output_path"

readonly run_id="$(read_output "$output_path" run_id)"
readonly project_id="$(read_output "$output_path" project_id)"
readonly vm_name="$(read_output "$output_path" trainer_instance_name)"
readonly zone="$(read_output "$output_path" trainer_zone)"
readonly artifact_uri="$(read_output "$output_path" run_artifact_uri)"
readonly training_image="$(read_output "$output_path" training_image)"

if [ "$run_id" != "$expected_run_id" ]; then
  echo "Applied run_id does not match the reviewed manifest." >&2
  exit 1
fi
if [ "$training_image" != "$expected_training_image" ]; then
  echo "Applied training image does not match the reviewed manifest." >&2
  exit 1
fi

checkpoint "INSTANCE" "checking $vm_name in $zone"
instance_status="$(gcloud compute instances describe "$vm_name" \
  --zone="$zone" --project="$project_id" --format='value(status)')"
if [ "$instance_status" != "RUNNING" ]; then
  echo "Training instance is not RUNNING after apply: $instance_status" >&2
  exit 1
fi
checkpoint "INSTANCE" "PASS status=$instance_status"

readonly timeout_seconds="${TRAINING_TIMEOUT_SECONDS:-14400}"
readonly poll_seconds="${TRAINING_POLL_SECONDS:-30}"
readonly startup_log="$evidence_dir/startup.log"
readonly training_evidence="$evidence_dir/training-evidence.json"

gcloud help compute instances get-serial-port-output >/dev/null
gcloud help storage cp >/dev/null

checkpoint "TRAINING" "waiting for terminal evidence at $artifact_uri"
deadline=$((SECONDS + timeout_seconds))
while :; do
  gcloud compute instances get-serial-port-output "$vm_name" \
    --port=1 --zone="$zone" --project="$project_id" --quiet >"$startup_log" || true

  if gcloud storage cp "$artifact_uri/training-evidence.json" "$training_evidence" \
      --project="$project_id" --quiet 2>/dev/null; then
    status="$(read_evidence "$training_evidence" status)"
    failed_stage="$(read_evidence "$training_evidence" failed_stage)"
    observed_dataset_sha256="$(read_evidence "$training_evidence" dataset_artifact_sha256)"

    if [ -n "$observed_dataset_sha256" ] && [ "$observed_dataset_sha256" != "$expected_dataset_sha256" ]; then
      checkpoint "DATASET_LINEAGE" "FAIL manifest changed after preflight"
      echo "expected=$expected_dataset_sha256 observed=$observed_dataset_sha256" >&2
      exit 1
    fi

    case "$status" in
      FINISHED)
        if [ -z "$observed_dataset_sha256" ]; then
          checkpoint "DATASET_LINEAGE" "FAIL terminal evidence omitted dataset manifest hash"
          exit 1
        fi
        checkpoint "DATASET_LINEAGE" "PASS dataset_artifact_sha256=$observed_dataset_sha256"
        checkpoint "TRAINING" "PASS terminal evidence=$training_evidence"
        break
        ;;
      FAILED)
        checkpoint "TRAINING" "FAIL failed_stage=${failed_stage:-unknown}"
        echo "Inspect $training_evidence and $startup_log" >&2
        exit 1
        ;;
    esac
  fi

  if [ "$SECONDS" -ge "$deadline" ]; then
    checkpoint "TRAINING" "FAIL timed out after ${timeout_seconds}s"
    echo "Inspect $startup_log" >&2
    exit 1
  fi
  sleep "$poll_seconds"
done

checkpoint "COMPLETE" "run_id=$run_id evidence_dir=$evidence_dir"
echo "The VM remains Terraform-managed. Destroy only from a separately reviewed destroy plan."
