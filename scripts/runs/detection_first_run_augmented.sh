#!/usr/bin/env bash
#
# Apply one reviewed detection training plan and collect its durable evidence.
#
# This script never generates a plan and never fabricates success from VM
# creation: it waits for the terminal training evidence the VM exports.
set -euo pipefail

: "${RUN_MANIFEST:?RUN_MANIFEST must name a reviewed run-manifest.json}"

readonly terraform_root="terraform/runs/detection"
readonly manifest_path="$RUN_MANIFEST"
if [ ! -f "$manifest_path" ]; then
  echo "Run manifest is missing: $manifest_path" >&2
  exit 1
fi

# Use this function to read one required non-secret field from the reviewed manifest.
read_manifest() {
  python3 - "$manifest_path" "$1" <<'PY'
import json
import sys

value = json.loads(open(sys.argv[1], encoding="utf-8").read())[sys.argv[2]]
if not isinstance(value, str) or not value:
    raise SystemExit(f"manifest field {sys.argv[2]!r} must be a non-empty string")
print(value)
PY
}

# Use this function to read one required value from the applied Terraform outputs.
read_output() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

value = json.loads(open(sys.argv[1], encoding="utf-8").read())[sys.argv[2]]["value"]
if not isinstance(value, str) or not value:
    raise SystemExit(f"terraform output {sys.argv[2]!r} must be a non-empty string")
print(value)
PY
}

readonly run_id="$(read_manifest run_id)"
readonly plan_path="$(read_manifest terraform_plan)"
readonly evidence_dir="$(dirname "$manifest_path")"
readonly project_id="cs-poc-kewg0kffb7uwobgq1rex2af"
readonly timeout_seconds="${TRAINING_TIMEOUT_SECONDS:-14400}"
readonly poll_seconds="${TRAINING_POLL_SECONDS:-30}"

if [ ! -f "$plan_path" ]; then
  echo "Reviewed Terraform plan is missing: $plan_path" >&2
  exit 1
fi

gcloud help compute instances get-serial-port-output >/dev/null
gcloud help storage cp >/dev/null

terraform -chdir="$terraform_root" apply -input=false "$plan_path"
readonly output_path="$evidence_dir/terraform-output.json"
terraform -chdir="$terraform_root" output -json >"$output_path"

# The VM name, zone, and evidence destination come from the applied outputs, so
# this script never re-derives a name Terraform already owns.
readonly vm_name="$(read_output "$output_path" trainer_instance_name)"
readonly zone="$(read_output "$output_path" trainer_zone)"
readonly artifact_uri="$(read_output "$output_path" run_artifact_uri)"

echo "Applied run $run_id as $vm_name in $zone; evidence will land in $artifact_uri"

deadline=$((SECONDS + timeout_seconds))
while :; do
  gcloud compute instances get-serial-port-output "$vm_name" --port=1 --zone="$zone" --project="$project_id" --quiet >"$evidence_dir/startup.log" || true
  if gcloud storage cp "$artifact_uri/training-evidence.json" "$evidence_dir/training-evidence.json" --project="$project_id" --quiet 2>/dev/null; then
    status="$(python3 -c 'import json,sys; print(json.loads(open(sys.argv[1], encoding="utf-8").read())["status"])' "$evidence_dir/training-evidence.json")"
    case "$status" in
      FINISHED)
        break
        ;;
      FAILED)
        # The VM exports evidence on failure too; stop here instead of waiting
        # out the timeout on a run that has already reported a terminal state.
        echo "Training reported FAILED; inspect $evidence_dir/training-evidence.json and $evidence_dir/startup.log" >&2
        exit 1
        ;;
    esac
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "Training evidence was not finalized before timeout; inspect $evidence_dir/startup.log" >&2
    exit 1
  fi
  sleep "$poll_seconds"
done

echo "Captured training evidence in $evidence_dir"
echo "The training VM is still running. Removing it is a Terraform lifecycle action:"
echo "  terraform -chdir=$terraform_root plan -destroy -out=<destroy-plan>   # review before applying"
