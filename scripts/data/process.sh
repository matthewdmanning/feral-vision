#!/usr/bin/env bash
# Materialize the DVC preprocessing and augmentation stages locally.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

cd "$DATA_SCRIPTS_ROOT"
configure_dvc_remote
uv run dvc repro preprocess augment "$@"
