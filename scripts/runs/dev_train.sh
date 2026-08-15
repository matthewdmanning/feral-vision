#!/usr/bin/env bash
set -euo pipefail

: "${TRAIN_DATA:?TRAIN_DATA must point to a staged dataset containing images, annotations, and dvc.lock}"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_dir/../.." && pwd)"
tracking_uri="${MLFLOW_TRACKING_URI:-http://localhost:5000}"
experiment_name="${MLFLOW_EXPERIMENT_NAME:-feral-vision}"
run_config_name="${RUN_CONFIG_NAME:-runs/baseline}"

cd "$repository_root"
test -d "$TRAIN_DATA/images"
test -d "$TRAIN_DATA/annotations"
test -f "$TRAIN_DATA/dvc.lock"

exec uv run --no-sync python -m feral_vision.training.trainer \
  --config-name "$run_config_name" \
  "data.root=$TRAIN_DATA" \
  "tracking.tracking_uri=$tracking_uri" \
  "tracking.experiment_name=$experiment_name"
