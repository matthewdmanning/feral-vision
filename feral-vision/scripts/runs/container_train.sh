#!/usr/bin/env bash
set -euo pipefail

: "${TRAIN_DATA:?TRAIN_DATA must name the staged Dataset Artifact payload}"
: "${DATASET_ARTIFACT_MANIFEST:?DATASET_ARTIFACT_MANIFEST must name dataset-artifact.json}"
: "${DATASET_ARTIFACT_SHA256:?DATASET_ARTIFACT_SHA256 must pin the staged dataset manifest}"
: "${MLFLOW_TRACKING_URI:?MLFLOW_TRACKING_URI must name the tracking service or local store}"

: "${TRAINING_DATA_BUCKET_URI:?TRAINING_DATA_BUCKET_URI must name the run output prefix}"

test -d "${TRAIN_DATA}/images"
test -d "${TRAIN_DATA}/annotations"
test -s "${DATASET_ARTIFACT_MANIFEST}"

# cloud_train.sh runs from RUN_OUTPUT_DIR and uploads everything under it.
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export CONFIG_DIR="$(cd "${here}/../../conf" && pwd)"
export CONFIG_NAME="runs/detection"
export RUN_OUTPUT_DIR="${RUN_OUTPUT_DIR:-/data/outputs}"
exec bash "${here}/cloud_train.sh" \
  "data.root=${TRAIN_DATA}" \
  "tracking.tracking_uri=${MLFLOW_TRACKING_URI}"
