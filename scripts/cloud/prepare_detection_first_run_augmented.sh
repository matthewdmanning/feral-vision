#!/usr/bin/env bash
set -euo pipefail

: "${MLFLOW_ARTIFACT_PREFIX:?MLFLOW_ARTIFACT_PREFIX must be the writable gs:// artifact prefix}"
: "${VM_SERVICE_ACCOUNT_EMAIL:?VM_SERVICE_ACCOUNT_EMAIL must be the reviewed VM identity}"

readonly project_id="cs-poc-kewg0kffb7uwobgq1rex2af"
readonly region="us-east4"
readonly repository="feral-docker"
readonly raw_prefix="${RAW_DATASET_ARTIFACT_PREFIX:-datasets/coco/train2017/raw-20260806-800-animals-v2}"
readonly run_id="${RUN_ID:-first-run-augmented-$(date -u +%Y%m%d-%H%M%S)}"
readonly artifact_dir="${ARTIFACT_DIR:-artifacts/detection_first_run_augmented/$run_id}"
readonly image_tag="${region}-docker.pkg.dev/${project_id}/${repository}/feral-vision-detection-first-run-augmented:${run_id}"
readonly raw_uri="gs://mobile-training-images/${raw_prefix}"
readonly variant_prefix="${VARIANT_ARTIFACT_PREFIX:-datasets/coco/train2017/${run_id}}"
readonly variant_uri="gs://mobile-training-images/${variant_prefix}"
readonly vm_name="feral-vision-detection-first-run-augmented-${run_id}"
readonly plan_path="$artifact_dir/terraform.tfplan"
readonly manifest_path="$artifact_dir/run-manifest.json"

mkdir -p "$artifact_dir"

gcloud help builds submit >/dev/null
gcloud help artifacts docker images describe >/dev/null
gcloud help storage ls >/dev/null
gcloud help storage objects describe >/dev/null

for required_object in payload/images payload/annotations dataset-artifact.json dataset-artifact.dvc; do
  gcloud storage ls "${raw_uri}/${required_object}" --project="$project_id" --quiet >/dev/null
done

if ! gcloud artifacts docker images describe "$image_tag" --project="$project_id" --format='value(image_summary.digest)' --quiet >"$artifact_dir/image-digest.txt"; then
  gcloud builds submit . --project="$project_id" --region="$region" --config=deploy/runs/detection_first_run_augmented/cloudbuild.training-image.yaml --substitutions="_BASE_IMAGE=us-east4-docker.pkg.dev/${project_id}/${repository}/feral-vision@sha256:e2847fd0979bd711f66b7b418262d9b98472cd8f1b905709c632f0f7ba6f8cce,_TRAINING_IMAGE=${image_tag}" --quiet
  gcloud artifacts docker images describe "$image_tag" --project="$project_id" --format='value(image_summary.digest)' --quiet >"$artifact_dir/image-digest.txt"
fi

readonly image_digest="$(tr -d '[:space:]' <"$artifact_dir/image-digest.txt")"
if [ -z "$image_digest" ]; then
  echo "Artifact Registry did not return an immutable image digest" >&2
  exit 1
fi
readonly training_image="${image_tag%@*}@${image_digest}"

if ! gcloud storage ls "${variant_uri}/dataset-artifact.dvc" --project="$project_id" --quiet >/dev/null; then
  gcloud builds submit . --project="$project_id" --region="$region" --config=deploy/runs/detection_first_run_augmented/cloudbuild.materialize-variant.yaml --substitutions="_TRAINING_IMAGE=${training_image},_RAW_DATASET_ARTIFACT_URI=${raw_uri},_VARIANT_ARTIFACT_PREFIX=${variant_prefix}" --quiet
fi

gcloud storage ls "${variant_uri}/payload/images" --project="$project_id" --quiet >/dev/null
gcloud storage ls "${variant_uri}/payload/annotations" --project="$project_id" --quiet >/dev/null
gcloud storage ls "${variant_uri}/dataset-artifact.json" --project="$project_id" --quiet >/dev/null
gcloud storage ls "${variant_uri}/dataset-artifact.dvc" --project="$project_id" --quiet >/dev/null
gcloud storage objects describe "${variant_uri}/dataset-artifact.dvc" --project="$project_id" --format='value(generation)' --quiet >"$artifact_dir/tracker-generation.txt"
readonly tracker_generation="$(tr -d '[:space:]' <"$artifact_dir/tracker-generation.txt")"
if [ -z "$tracker_generation" ]; then
  echo "Dataset Variant tracker must resolve to an object generation" >&2
  exit 1
fi
readonly data_reference="${variant_uri}/dataset-artifact.dvc#${tracker_generation}"

RUN_ID="$run_id" \
TRAINING_IMAGE="$training_image" \
RAW_URI="$raw_uri" \
VARIANT_PREFIX="$variant_prefix" \
DATA_REFERENCE="$data_reference" \
MLFLOW_ARTIFACT_PREFIX="$MLFLOW_ARTIFACT_PREFIX" \
VM_SERVICE_ACCOUNT_EMAIL="$VM_SERVICE_ACCOUNT_EMAIL" \
VM_NAME="$vm_name" \
TERRAFORM_PLAN="$plan_path" \
python3 - "$manifest_path" <<'PY'
import json
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "run_id": os.environ["RUN_ID"],
            "training_image": os.environ["TRAINING_IMAGE"],
            "raw_dataset_artifact_uri": os.environ["RAW_URI"],
            "dataset_artifact_prefix": os.environ["VARIANT_PREFIX"],
            "data_reference": os.environ["DATA_REFERENCE"],
            "mlflow_tracking_uri": "http://127.0.0.1:5000",
            "mlflow_artifact_prefix": os.environ["MLFLOW_ARTIFACT_PREFIX"],
            "service_account_email": os.environ["VM_SERVICE_ACCOUNT_EMAIL"],
            "vm_name": os.environ["VM_NAME"],
            "terraform_plan": os.environ["TERRAFORM_PLAN"],
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
PY

terraform -chdir=terraform/runs/detection_first_run_augmented init -reconfigure -input=false
terraform -chdir=terraform/runs/detection_first_run_augmented plan -input=false -out="$plan_path" -var="project_id=$project_id" -var="vm_name=$vm_name" -var="training_image=$training_image" -var="dataset_artifact_prefix=$variant_prefix" -var="data_reference=$data_reference" -var="mlflow_artifact_prefix=$MLFLOW_ARTIFACT_PREFIX" -var="run_id=$run_id" -var="service_account_email=$VM_SERVICE_ACCOUNT_EMAIL"

echo "Prepared immutable run manifest: $manifest_path"
echo "Review Terraform plan before running scripts/runs/detection_first_run_augmented.sh"
