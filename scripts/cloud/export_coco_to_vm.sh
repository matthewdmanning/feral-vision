#!/usr/bin/env bash
set -euo pipefail

: "${COCO_MAX_EPOCHS:?COCO_MAX_EPOCHS must be set}"
: "${COCO_BATCH_SIZE:?COCO_BATCH_SIZE must be set}"
: "${COCO_EXPORT_DIR:?COCO_EXPORT_DIR must be set}"

uv run --with fiftyone python -c '
from pathlib import Path
import os

from scripts.pull_coco_train2017 import export_coco_train2017

export_coco_train2017(
    max_epochs=int(os.environ["COCO_MAX_EPOCHS"]),
    batch_size=int(os.environ["COCO_BATCH_SIZE"]),
    export_dir=Path(os.environ["COCO_EXPORT_DIR"]),
)
'
