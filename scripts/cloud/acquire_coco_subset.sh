#!/bin/sh
set -eu

: "${COCO_MAX_EPOCHS:?COCO_MAX_EPOCHS must be set}"
: "${COCO_BATCH_SIZE:?COCO_BATCH_SIZE must be set}"

cd /opt/feral-vision

payload_dir="${DATASET_PAYLOAD_DIR:-/workspace/payload}"
input_path="${DATASET_INPUT_PATH:-/workspace/dataset-input.json}"

python3 - "$payload_dir" <<'PY'
import os
import sys
from pathlib import Path

from scripts.pull_coco_train2017 import COCO_ANIMAL_CLASSES, export_coco_train2017

export_coco_train2017(
    max_epochs=int(os.environ["COCO_MAX_EPOCHS"]),
    batch_size=int(os.environ["COCO_BATCH_SIZE"]),
    export_dir=Path(sys.argv[1]),
)
PY

python3 - "$input_path" <<'PY'
import json
import os
import sys
from pathlib import Path

max_epochs = int(os.environ["COCO_MAX_EPOCHS"])
batch_size = int(os.environ["COCO_BATCH_SIZE"])
metadata = {
    "dataset": "COCO 2017 train animal subset",
    "source": "FiftyOne coco-2017 train detections",
    "provenance": {
        "classes": [
            "bird", "cat", "dog", "horse", "sheep", "cow", "elephant",
            "bear", "zebra", "giraffe",
        ],
        "max_epochs": max_epochs,
        "batch_size": batch_size,
        "max_samples": max_epochs * batch_size,
        "random_seed": None,
    },
}
Path(sys.argv[1]).write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
PY
