#!/usr/bin/env bash
# Register prepared data in DVC's GCS remote and publish its cloud-side tracker.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

DATA_ROOT="${DATA_ROOT:-${DATA_SCRIPTS_ROOT}/data}"
DATA_URI="$(gcs_data_uri)"

require_command gcloud

cd "$DATA_SCRIPTS_ROOT"
configure_dvc_remote
uv run dvc push "$@"

gcloud storage rsync --recursive "$DATA_ROOT" "$DATA_URI"
gcloud storage cp dvc.lock "${DATA_URI%/}/dvc.lock"
