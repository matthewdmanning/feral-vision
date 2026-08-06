#!/usr/bin/env bash
set -euo pipefail

: "${GCS_BUCKET:?GCS_BUCKET must name the dataset-only bucket}"
: "${RAW_DATASET_ARTIFACT_URI:?RAW_DATASET_ARTIFACT_URI must name the immutable raw Artifact prefix}"
: "${VARIANT_ARTIFACT_PREFIX:?VARIANT_ARTIFACT_PREFIX must name a new immutable Variant prefix}"

workspace_dir="$(mktemp -d)"
trap 'rm -rf "$workspace_dir"' EXIT
raw_root="$workspace_dir/raw"
labels_root="$workspace_dir/labels"
variant_root="$workspace_dir/variant"
input_path="$workspace_dir/dataset-input.json"

gcloud storage rsync --recursive --checksums-only "${RAW_DATASET_ARTIFACT_URI}/payload" "$raw_root" --quiet
gcloud storage cp "${RAW_DATASET_ARTIFACT_URI}/dataset-artifact.json" "$workspace_dir/raw-manifest.json" --quiet

RAW_MANIFEST="$workspace_dir/raw-manifest.json" \
DATASET_INPUT="$input_path" \
LABELS_ROOT="$labels_root" \
RAW_ROOT="$raw_root" \
VARIANT_ROOT="$variant_root" \
python3 - <<'PY'
import json
import os
from pathlib import Path

import yaml

from feral_vision.data.augmentations import materialize_detection_variant
from feral_vision.data.coco_detection import convert_coco_cat_vs_not_cat_detections

raw_manifest = json.loads(Path(os.environ["RAW_MANIFEST"]).read_text())
raw_root = Path(os.environ["RAW_ROOT"])
labels_root = Path(os.environ["LABELS_ROOT"])
variant_root = Path(os.environ["VARIANT_ROOT"])
augmentation = yaml.safe_load(
    Path("/workspace/conf/augmentation/coco_animals_detection_first_run_augmented.yaml").read_text()
)

convert_coco_cat_vs_not_cat_detections(
    raw_root / "annotations" / "instances.json", raw_root / "images", labels_root
)
source_root = Path(os.environ["RAW_ROOT"]) / "yolo-source"
source_root.mkdir()
(source_root / "images").symlink_to(raw_root / "images", target_is_directory=True)
(source_root / "annotations").symlink_to(labels_root, target_is_directory=True)
materialize_detection_variant(
    source_root, variant_root, augmentation["ops"], seed=augmentation["seed"]
)
Path(os.environ["DATASET_INPUT"]).write_text(
    json.dumps(
        {
            "dataset": raw_manifest["dataset"],
            "source": raw_manifest["source"],
            "provenance": {
                **raw_manifest["provenance"],
                "class_contract": {"0": "cat", "1": "not-cat"},
            },
        },
        indent=2,
        sort_keys=True,
    )
    + "\n"
)
PY

GCS_BUCKET="$GCS_BUCKET" \
VARIANT_ARTIFACT_PREFIX="$VARIANT_ARTIFACT_PREFIX" \
VARIANT_ROOT="$variant_root" \
DATASET_INPUT="$input_path" \
RAW_DATASET_ARTIFACT_URI="$RAW_DATASET_ARTIFACT_URI" \
python3 - <<'PY'
import json
import os
from pathlib import Path

import yaml
from google.cloud import storage

from feral_vision.data.dataset_artifact import publish_dataset_variant_artifact

augmentation = yaml.safe_load(
    Path("/workspace/conf/augmentation/coco_animals_detection_first_run_augmented.yaml").read_text()
)
publish_dataset_variant_artifact(
    storage.Client(),
    bucket_name=os.environ["GCS_BUCKET"],
    artifact_prefix=os.environ["VARIANT_ARTIFACT_PREFIX"],
    payload_root=Path(os.environ["VARIANT_ROOT"]),
    input_path=Path(os.environ["DATASET_INPUT"]),
    source_artifact_uri=os.environ["RAW_DATASET_ARTIFACT_URI"],
    augmentation_recipe={
        "name": augmentation["name"],
        "seed": augmentation["seed"],
        "ops": augmentation["ops"],
    },
)
PY

tracker_dir="$workspace_dir/tracker"
mkdir -p "$tracker_dir"
cd "$tracker_dir"
dvc init --no-scm
dvc import-url --no-download --version-aware "gs://${GCS_BUCKET}/${VARIANT_ARTIFACT_PREFIX}/payload" dataset-artifact
grep -q "version_id:" dataset-artifact.dvc

GCS_BUCKET="$GCS_BUCKET" \
VARIANT_ARTIFACT_PREFIX="$VARIANT_ARTIFACT_PREFIX" \
TRACKER_PATH="$tracker_dir/dataset-artifact.dvc" \
python3 - <<'PY'
import os
from pathlib import Path

from google.cloud import storage
from feral_vision.data.dataset_artifact import publish_dataset_tracker

publish_dataset_tracker(
    storage.Client(),
    bucket_name=os.environ["GCS_BUCKET"],
    artifact_prefix=os.environ["VARIANT_ARTIFACT_PREFIX"],
    tracker_path=Path(os.environ["TRACKER_PATH"]),
)
PY
