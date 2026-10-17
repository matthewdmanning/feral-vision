#!/usr/bin/env bash
set -euo pipefail

# Local Feral Vision preview launcher for this checkout.
cd "$(dirname "${BASH_SOURCE[0]}")/.."

exec uv run --frozen python -c \
  "from tools.augmentation_preview_app import start_augmentation_preview_server; start_augmentation_preview_server('tests/fixtures/images', port=8765)"
