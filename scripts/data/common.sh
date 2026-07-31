#!/usr/bin/env bash
# Shared cloud-data environment checks. Source this file; do not execute it.

set -euo pipefail

DATA_SCRIPTS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DVC_REMOTE_NAME="${DVC_REMOTE_NAME:-gcs}"
GCS_BUCKET="${GCS_BUCKET:?GCS_BUCKET must name the durable DVC Cloud Storage bucket}"
GCS_DATA_PREFIX="${GCS_DATA_PREFIX:-datasets/feral-vision}"

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "required command is unavailable: $1" >&2
        exit 1
    }
}

configure_dvc_remote() {
    require_command uv
    uv run dvc remote modify --local "$DVC_REMOTE_NAME" \
        url "gs://${GCS_BUCKET}/dvc"
}

gcs_data_uri() {
    printf 'gs://%s/%s\n' "$GCS_BUCKET" "${GCS_DATA_PREFIX#/}"
}
