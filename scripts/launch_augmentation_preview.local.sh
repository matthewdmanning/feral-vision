#!/usr/bin/env bash
set -euo pipefail

# Local Feral Vision preview launcher for this checkout.
cd /root/feral-vision

exec /root/feral-vision/.venv/bin/python -c \
  "from feral_vision.data.augmentation_preview_app import start_augmentation_preview_server; start_augmentation_preview_server('/root/feral-vision/tests/fixtures/images', port=8765)"
