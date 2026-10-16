#!/bin/sh
# Publish a Dataset Artifact: plain payload/ and dataset-artifact.json, which
# lists every payload file with its SHA-256 and Cloud Storage generation.
set -eu

: "${GCS_URI_PREFIX:?GCS_URI_PREFIX must be set}"

: "${TRAINING_DATA_BUCKET_URI:?TRAINING_DATA_BUCKET_URI must be set}"
: "${DATASET_ARTIFACT_PREFIX:?DATASET_ARTIFACT_PREFIX must be set}"

payload_dir="${DATASET_PAYLOAD_DIR:-/workspace/payload}"
input_path="${DATASET_INPUT_PATH:-/workspace/dataset-input.json}"
retention_days="${DATASET_RETENTION_DAYS:-365}"

python3 - "$payload_dir" "$input_path" "$retention_days" <<'PY'
import os
import sys
from pathlib import Path

from google.cloud import storage

from feral_vision.data.dataset_artifact import publish_dataset_artifact

print(publish_dataset_artifact(
    storage.Client(),
    bucket_name=os.environ["TRAINING_DATA_BUCKET_URI"].removeprefix(os.environ["GCS_URI_PREFIX"]).rstrip("/"),
    artifact_prefix=os.environ["DATASET_ARTIFACT_PREFIX"],
    payload_root=Path(sys.argv[1]),
    input_path=Path(sys.argv[2]),
    retention_days=int(sys.argv[3]),
))
PY
