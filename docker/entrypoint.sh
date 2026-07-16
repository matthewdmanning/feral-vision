#!/usr/bin/env bash
# Training entrypoint: sync data from GCS → train → push results to GCS.
#
# Required env vars:
#   GCS_BUCKET   - GCS bucket name (no gs:// prefix), e.g. "my-feral-bucket"
#
# Optional env vars:
#   DATA_DIR     - local SSD mount (default: /data)
#   HYDRA_OVERRIDES - extra Hydra CLI overrides passed to the trainer
#
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
GCS_BUCKET="${GCS_BUCKET:?GCS_BUCKET env var required}"

echo "=== [1/4] Syncing images from gs://${GCS_BUCKET}/images/ ==="
gcloud storage rsync -r "gs://${GCS_BUCKET}/images/" "${DATA_DIR}/images/"

echo "=== [2/4] Syncing labels from gs://${GCS_BUCKET}/labels/ ==="
gcloud storage rsync -r "gs://${GCS_BUCKET}/labels/" "${DATA_DIR}/labels/"

echo "=== [3/4] Starting MLflow tracking server ==="
mlflow server \
    --backend-store-uri "sqlite:///${DATA_DIR}/mlflow/mlflow.db" \
    --default-artifact-root "gs://${GCS_BUCKET}/mlflow/" \
    --host 0.0.0.0 \
    --port 5000 &
MLFLOW_PID=$!
sleep 3  # allow server to start

echo "=== [4/4] Starting training ==="
python -m feral_vision.training.train \
    data=coco_train2017 \
    train.data_dir="${DATA_DIR}" \
    tracking.tracking_uri="http://localhost:5000" \
    ${HYDRA_OVERRIDES:-}

echo "=== Pushing runs to gs://${GCS_BUCKET}/runs/ ==="
gcloud storage cp -r "${DATA_DIR}/runs/" "gs://${GCS_BUCKET}/runs/"

echo "=== Done. ==="
kill $MLFLOW_PID 2>/dev/null || true
