#!/usr/bin/env bash
set -euo pipefail

: "${TRAIN_DATA:?TRAIN_DATA must name the staged Dataset Variant Artifact payload}"
: "${MLFLOW_TRACKING_URI:?MLFLOW_TRACKING_URI must name the running MLflow tracking server}"
: "${RUN_CONFIG_NAME:=runs/detection}"

test -d "${TRAIN_DATA}/images"
test -d "${TRAIN_DATA}/annotations"
test -f "${TRAIN_DATA}/dvc.lock"

mkdir -p mlruns
mlflow server \
  --host 127.0.0.1 \
  --port 5000 \
  --backend-store-uri ./mlruns >mlruns/server.log 2>&1 &
mlflow_server_pid=$!

cleanup_mlflow() {
  kill "$mlflow_server_pid" >/dev/null 2>&1 || true
}
trap cleanup_mlflow EXIT

sleep 2
python -c 'import urllib.request; urllib.request.urlopen("http://localhost:5000/version", timeout=5)'

uv run --no-sync python -m feral_vision.training.trainer \
  --config-name "${RUN_CONFIG_NAME}" \
  "data.root=${TRAIN_DATA}" \
  "tracking.tracking_uri=${MLFLOW_TRACKING_URI}"
