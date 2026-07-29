#!/usr/bin/env bash
set -euo pipefail

train_data="${TRAIN_DATA:-/data}"

uv run --no-sync python -m feral_vision.data.augmentations "data.root=$train_data"
uv run --no-sync python -m feral_vision.training.trainer "data.root=$train_data"
