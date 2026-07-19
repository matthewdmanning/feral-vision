#!/usr/bin/env bash
# GCE container workflow: stage data on SSD, run MLflow, and train.
#
# Required env vars:
#   GCS_BUCKET   - GCS bucket name (no gs:// prefix), e.g. "my-feral-bucket"
#
# Optional env vars:
#   DATA_DIR     - local SSD mount (default: /data)
#   TRAIN_DATA   - Hydra data variant (default: default)
#   GCS_DATA_PREFIX - GCS prefix containing images/ and annotations/
#   MLFLOW_ARTIFACT_PREFIX - GCS prefix for MLflow artifacts
#   MLFLOW_PORT  - local MLflow sidecar port (default: 5000)
#   MLFLOW_STARTUP_DELAY_SECONDS - wait before training starts (default: 3)
#   HYDRA_OVERRIDES - extra Hydra CLI overrides passed to the trainer
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
GCS_BUCKET="${GCS_BUCKET:?GCS_BUCKET env var required}"
TRAIN_DATA="${TRAIN_DATA:-default}"
GCS_DATA_PREFIX="${GCS_DATA_PREFIX:-}"
MLFLOW_ARTIFACT_PREFIX="${MLFLOW_ARTIFACT_PREFIX:?MLFLOW_ARTIFACT_PREFIX env var required}"
MLFLOW_PORT="${MLFLOW_PORT:-5000}"
MLFLOW_STARTUP_DELAY_SECONDS="${MLFLOW_STARTUP_DELAY_SECONDS:-3}"

if [[ -n "${GCS_DATA_PREFIX}" ]]; then
    GCS_DATA_PREFIX="${GCS_DATA_PREFIX%/}/"
fi
MLFLOW_ARTIFACT_PREFIX="${MLFLOW_ARTIFACT_PREFIX%/}"

echo "=== [1/4] Syncing images from gs://${GCS_BUCKET}/${GCS_DATA_PREFIX}images/ ==="
gcloud storage rsync -r \
    "gs://${GCS_BUCKET}/${GCS_DATA_PREFIX}images/" \
    "${DATA_DIR}/images/"

echo "=== [2/4] Syncing annotations from gs://${GCS_BUCKET}/${GCS_DATA_PREFIX}annotations/ ==="
gcloud storage rsync -r \
    "gs://${GCS_BUCKET}/${GCS_DATA_PREFIX}annotations/" \
    "${DATA_DIR}/annotations/"

echo "=== [3/4] Starting MLflow tracking server ==="
mkdir -p "${DATA_DIR}/mlflow"
mlflow server \
    --backend-store-uri "sqlite:///${DATA_DIR}/mlflow/mlflow.db" \
    --default-artifact-root "gs://${GCS_BUCKET}/${MLFLOW_ARTIFACT_PREFIX}/" \
    --host 0.0.0.0 \
    --port "${MLFLOW_PORT}" &
MLFLOW_PID=$!
trap 'kill "${MLFLOW_PID}" 2>/dev/null || true' EXIT
sleep "${MLFLOW_STARTUP_DELAY_SECONDS}"

echo "=== [4/4] Starting training ==="
python -m feral_vision.training.trainer \
    data="${TRAIN_DATA}" \
    data.root="${DATA_DIR}" \
    tracking.tracking_uri="http://localhost:${MLFLOW_PORT}" \
    ${HYDRA_OVERRIDES:-}

echo "=== Done. ==="
