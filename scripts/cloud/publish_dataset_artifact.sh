#!/bin/sh
set -eu

: "${GCS_BUCKET:?GCS_BUCKET must be set}"
: "${DATASET_ARTIFACT_PREFIX:?DATASET_ARTIFACT_PREFIX must be set}"

payload_dir="${DATASET_PAYLOAD_DIR:-/workspace/payload}"
input_path="${DATASET_INPUT_PATH:-/workspace/dataset-input.json}"

payload_uri="$(python3 - "$payload_dir" "$input_path" <<'PY'
import os
import sys
from pathlib import Path

from google.cloud import storage
from feral_vision.data.dataset_artifact import publish_dataset_artifact

print(
    publish_dataset_artifact(
        storage.Client(),
        bucket_name=os.environ["GCS_BUCKET"],
        artifact_prefix=os.environ["DATASET_ARTIFACT_PREFIX"],
        payload_root=Path(sys.argv[1]),
        input_path=Path(sys.argv[2]),
    )
)
PY
)"

tracker_dir="$(mktemp -d)"
trap 'rm -rf "$tracker_dir"' EXIT
cd "$tracker_dir"
dvc init --no-scm
dvc import-url --no-download --version-aware "$payload_uri" dataset-artifact
grep -q "version_id:" dataset-artifact.dvc

python3 - "$(pwd)/dataset-artifact.dvc" <<'PY'
import os
import sys
from pathlib import Path

from google.cloud import storage
from feral_vision.data.dataset_artifact import publish_dataset_tracker

publish_dataset_tracker(
    storage.Client(),
    bucket_name=os.environ["GCS_BUCKET"],
    artifact_prefix=os.environ["DATASET_ARTIFACT_PREFIX"],
    tracker_path=Path(sys.argv[1]),
)
PY
