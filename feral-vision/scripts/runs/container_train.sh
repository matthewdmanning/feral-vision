#!/usr/bin/env bash
set -euo pipefail

: "${TRAIN_DATA:?TRAIN_DATA must name the staged Dataset Artifact payload}"
: "${DATASET_ARTIFACT_MANIFEST:?DATASET_ARTIFACT_MANIFEST must name dataset-artifact.json}"
: "${DATASET_ARTIFACT_SHA256:?DATASET_ARTIFACT_SHA256 must pin the staged dataset manifest}"
: "${MLFLOW_TRACKING_URI:?MLFLOW_TRACKING_URI must name the tracking service or local store}"

readonly run_config_name="runs/detection"

test -d "${TRAIN_DATA}/images"
test -d "${TRAIN_DATA}/annotations"
test -s "${DATASET_ARTIFACT_MANIFEST}"

exec uv run --frozen --no-sync python -m sightkit_learn.training.trainer \
  --config-dir "$(cd "$(dirname "${BASH_SOURCE[0]}")/../../conf" && pwd)" \
  --config-name "${run_config_name}" \
  "data.root=${TRAIN_DATA}" \
  "tracking.tracking_uri=${MLFLOW_TRACKING_URI}"
