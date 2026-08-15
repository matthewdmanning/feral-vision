#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd -- "$script_dir/../.." && pwd)"
state_dir="${FERAL_VISION_MLFLOW_DIR:-$repository_root/.mlflow}"
state_dir="$(realpath -m -- "$state_dir")"
host="${MLFLOW_HOST:-127.0.0.1}"
port="${MLFLOW_PORT:-5000}"

mkdir -p "$state_dir/artifacts"
backend_store_uri="sqlite:////${state_dir#/}/mlflow.db"

exec uv run --no-sync mlflow server \
  --host "$host" \
  --port "$port" \
  --workers 1 \
  --backend-store-uri "$backend_store_uri" \
  --default-artifact-root "mlflow-artifacts:/" \
  --artifacts-destination "$state_dir/artifacts"
