#!/usr/bin/env bash
set -euo pipefail

: "${MAX_EPOCHS:?MAX_EPOCHS must be set}"
: "${BATCH_SIZE:?BATCH_SIZE must be set}"
: "${EXPORT_DIR:?EXPORT_DIR must be set}"

uv run --with fiftyone python -c '
from pathlib import Path
import os

from scripts.pull_coco_train2017 import export_coco_train2017

export_coco_train2017(
    max_epochs=int(os.environ["MAX_EPOCHS"]),
    batch_size=int(os.environ["BATCH_SIZE"]),
    export_dir=Path(os.environ["EXPORT_DIR"]),
)
'
