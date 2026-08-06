#!/bin/sh
set -eu

: "${GCS_BUCKET:?GCS_BUCKET must be set}"
: "${DATASET_ARTIFACT_PREFIX:?DATASET_ARTIFACT_PREFIX must be set}"

payload_dir="${DATASET_PAYLOAD_DIR:-/workspace/payload}"
input_path="${DATASET_INPUT_PATH:-/workspace/dataset-input.json}"

if [ -n "${DATASET_INPUT_JSON:-}" ]; then
  printf '%s\n' "$DATASET_INPUT_JSON" > "$input_path"
fi

payload_uri="$(python3 - "$payload_dir" "$input_path" <<'PY'
import os
import sys
from pathlib import Path

from google.cloud import storage
from feral_vision.data.dataset_artifact import (
    build_dataset_artifact,
    load_dataset_input,
    payload_files,
    publish_dataset_artifact,
)

bucket_name = os.environ["GCS_BUCKET"]
artifact_prefix = os.environ["DATASET_ARTIFACT_PREFIX"].strip("/")
payload_root = Path(sys.argv[1])
input_path = Path(sys.argv[2])
if os.environ.get("DATASET_PAYLOAD_ALREADY_PUBLISHED") == "1":
    files = payload_files(payload_root)
    manifest = build_dataset_artifact(
        load_dataset_input(input_path), payload_file_count=len(files)
    )
    storage.Client().bucket(bucket_name).blob(
        f"{artifact_prefix}/dataset-artifact.json"
    ).upload_from_string(
        __import__("json").dumps(manifest, indent=2, sort_keys=True) + "\n",
        content_type="application/json",
        if_generation_match=0,
    )
    print(f"gs://{bucket_name}/{artifact_prefix}/payload")
else:
    print(
        publish_dataset_artifact(
            storage.Client(),
            bucket_name=bucket_name,
            artifact_prefix=artifact_prefix,
            payload_root=payload_root,
            input_path=input_path,
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
