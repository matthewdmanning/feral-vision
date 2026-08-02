#!/usr/bin/env bash
set -euo pipefail

: "${TRAIN_DATA:?TRAIN_DATA must name the staged Dataset Variant Artifact payload}"
: "${MLFLOW_TRACKING_URI:?MLFLOW_TRACKING_URI must name the managed tracking service}"

test -d "${TRAIN_DATA}/images"
test -d "${TRAIN_DATA}/annotations"
test -f "${TRAIN_DATA}/dataset-artifact.json"
test -f "${TRAIN_DATA}/dataset-artifact.dvc"

exec uv run --no-sync python -m feral_vision.training.trainer \
  --config-name runs/detection \
  "data.root=${TRAIN_DATA}" \
  "tracking.tracking_uri=${MLFLOW_TRACKING_URI}"
