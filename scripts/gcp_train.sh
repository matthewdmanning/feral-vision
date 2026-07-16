#!/usr/bin/env bash
set -euo pipefail

: "${GCP_PROJECT:?GCP_PROJECT must be set}"
: "${GCS_BUCKET:?GCS_BUCKET must be set}"

VM_NAME="${VM_NAME:-feral-vision-trainer}"
VM_ZONE="${VM_ZONE:-us-central1-a}"
EPOCHS="${EPOCHS:-1}"
MODE="${MODE:-docker}"
STOP_VM="${STOP_VM:-true}"
REGION="${REGION:-us-central1}"
REPO="${REPO:-feral-vision}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

IMAGE_URI="${REGION}-docker.pkg.dev/${GCP_PROJECT}/${REPO}/feral-vision-gcp:${IMAGE_TAG}"

teardown() {
  if [[ "$STOP_VM" == "true" ]]; then
    echo "Stopping VM..."
    gcloud compute instances stop "$VM_NAME" --zone="$VM_ZONE" --project="$GCP_PROJECT" --async
  fi
}
trap teardown EXIT

STATUS=$(gcloud compute instances describe "$VM_NAME" \
  --zone="$VM_ZONE" --project="$GCP_PROJECT" --format="value(status)")

if [[ "$STATUS" == "TERMINATED" ]]; then
  echo "Starting VM $VM_NAME..."
  gcloud compute instances start "$VM_NAME" --zone="$VM_ZONE" --project="$GCP_PROJECT"
  gcloud compute ssh "$VM_NAME" --zone="$VM_ZONE" --project="$GCP_PROJECT" \
    --command="echo ready" --ssh-flag="-o ConnectTimeout=60"
elif [[ "$STATUS" != "RUNNING" ]]; then
  echo "VM is in unexpected state: $STATUS" >&2
  exit 1
fi

if [[ "$MODE" == "docker" ]]; then
  gcloud compute ssh "$VM_NAME" --zone="$VM_ZONE" --project="$GCP_PROJECT" --command="
    docker pull ${IMAGE_URI} && \
    docker run --gpus all --rm \
      -e GCP_PROJECT=${GCP_PROJECT} \
      -e GCS_BUCKET=${GCS_BUCKET} \
      -e HYDRA_OVERRIDES='train.epochs=${EPOCHS}' \
      ${IMAGE_URI}
  "
elif [[ "$MODE" == "direct" ]]; then
  gcloud compute ssh "$VM_NAME" --zone="$VM_ZONE" --project="$GCP_PROJECT" --command="
    cd /workspace && \
    GCS_BUCKET=${GCS_BUCKET} dvc pull && \
    uv run python -m feral_vision.training.trainer train.epochs=${EPOCHS}
  "
else
  echo "Unknown MODE: $MODE (use 'docker' or 'direct')" >&2
  exit 1
fi
