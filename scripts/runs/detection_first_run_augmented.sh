#!/usr/bin/env bash
set -euo pipefail

: "${RUN_MANIFEST:?RUN_MANIFEST must name a reviewed run-manifest.json}"

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

readonly run_id="$(read_manifest run_id)"
readonly plan_path="$(read_manifest terraform_plan)"
readonly artifact_prefix="$(read_manifest mlflow_artifact_prefix)"
readonly vm_name="$(read_manifest vm_name)"
readonly evidence_dir="$(dirname "$manifest_path")"
readonly project_id="cs-poc-kewg0kffb7uwobgq1rex2af"
readonly zone="us-east4-c"
readonly timeout_seconds="${TRAINING_TIMEOUT_SECONDS:-14400}"
readonly poll_seconds="${TRAINING_POLL_SECONDS:-30}"

if [ ! -f "$plan_path" ]; then
  echo "Reviewed Terraform plan is missing: $plan_path" >&2
  exit 1
fi

gcloud help compute instances get-serial-port-output >/dev/null
gcloud help storage cp >/dev/null
terraform -chdir=terraform/runs/detection_first_run_augmented apply -input=false "$plan_path"
terraform -chdir=terraform/runs/detection_first_run_augmented output -json >"$evidence_dir/terraform-output.json"
deadline=$((SECONDS + timeout_seconds))
while :; do
  gcloud compute instances get-serial-port-output "$vm_name" --port=1 --zone="$zone" --project="$project_id" --quiet >"$evidence_dir/startup.log"
  if gcloud storage cp "$artifact_prefix/detection_first_run_augmented/$run_id/training-evidence.json" "$evidence_dir/training-evidence.json" --project="$project_id" --quiet
  then
    if python3 - "$evidence_dir/training-evidence.json" <<'PY'
import json
import sys

raise SystemExit(0 if json.loads(open(sys.argv[1], encoding="utf-8").read())["status"] == "FINISHED" else 1)
PY
    then
      break
    fi
  fi
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "Training evidence was not finalized before timeout; inspect $evidence_dir/startup.log" >&2
    exit 1
  fi
  sleep "$poll_seconds"
done

gcloud storage cp "$evidence_dir/training-evidence.json" "$artifact_prefix/detection_first_run_augmented/$run_id/training-evidence.json" --project="$project_id" --quiet
echo "Captured training evidence in $evidence_dir"
