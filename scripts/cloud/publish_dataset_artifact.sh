#!/bin/sh
set -eu

: "${GCS_BUCKET:?GCS_BUCKET must be set}"
: "${DATASET_ARTIFACT_PREFIX:?DATASET_ARTIFACT_PREFIX must be set}"

payload_dir="${DATASET_PAYLOAD_DIR:-/workspace/payload}"
workspace_dir="${DVC_WORKSPACE_DIR:-/workspace}"

case "$payload_dir" in
  "$workspace_dir"/*) ;;
  *)
    echo "DATASET_PAYLOAD_DIR must be inside DVC_WORKSPACE_DIR" >&2
    exit 1
    ;;
esac

cd "$workspace_dir"
dvc init --no-scm
dvc remote add --default dataset "gs://${GCS_BUCKET}/${DATASET_ARTIFACT_PREFIX}"

lock_path="$(python3 - "$payload_dir" "$workspace_dir" <<'PY'
import sys
from pathlib import Path

from feral_vision.data.dataset_artifact import version_dataset

print(version_dataset(Path(sys.argv[1]), workspace=Path(sys.argv[2])))
PY
)"

dvc push

python3 - "$lock_path" <<'PY'
import os
import sys
from pathlib import Path

from google.cloud import storage
from feral_vision.data.dataset_artifact import publish_dataset_lock

print(publish_dataset_lock(
    storage.Client(),
    bucket_name=os.environ["GCS_BUCKET"],
    artifact_prefix=os.environ["DATASET_ARTIFACT_PREFIX"],
    lock_path=Path(sys.argv[1]),
))
PY
