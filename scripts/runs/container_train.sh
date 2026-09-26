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

python - "${DATASET_ARTIFACT_MANIFEST}" "${DATASET_ARTIFACT_SHA256}" <<'PY'
import hashlib
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
expected_sha256 = sys.argv[2]
raw = path.read_bytes()
manifest = json.loads(raw)
if not isinstance(manifest, dict) or not manifest:
    raise SystemExit("dataset-artifact.json must contain a non-empty JSON object")
actual_sha256 = hashlib.sha256(raw).hexdigest()
if actual_sha256 != expected_sha256:
    raise SystemExit(
        f"dataset-artifact.json SHA-256 mismatch: expected {expected_sha256}, got {actual_sha256}"
    )
PY

exec uv run --frozen --no-sync python -m feral_vision.training.trainer \
  --config-name "${run_config_name}" \
  "data.root=${TRAIN_DATA}" \
  "tracking.tracking_uri=${MLFLOW_TRACKING_URI}"
