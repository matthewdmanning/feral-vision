#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <conf/model/*.yaml>" >&2
  exit 2
fi

if [[ -z "${GCS_BUCKET:-}" ]]; then
  echo "GCS_BUCKET must name the destination bucket." >&2
  exit 2
fi

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
model_config="$1"
if [[ "$model_config" != /* ]]; then
  model_config="$project_root/$model_config"
fi

if [[ ! -f "$model_config" ]]; then
  echo "model config does not exist: $model_config" >&2
  exit 2
fi

mapfile -t model_values < <(
  cd "$project_root"
  uv run --no-sync python -c '
from omegaconf import OmegaConf
import sys

config = OmegaConf.load(sys.argv[1])
print(config.architecture.source)
print(config.architecture.id)
' "$model_config"
)

model_source="${model_values[0]:-}"
model_id="${model_values[1]:-}"
if [[ "$model_source" != "ultralytics" || -z "$model_id" ]]; then
  echo "only ultralytics model configs with architecture.id can be staged." >&2
  exit 2
fi

model_path="$(
  cd "$project_root"
  uv run --no-sync python -c '
from ultralytics import YOLO
from pathlib import Path
import sys

print(Path(YOLO(sys.argv[1], verbose=False).ckpt_path).resolve())
' "$model_id" | tail -n 1
)"

if [[ ! -f "$model_path" ]]; then
  echo "Ultralytics did not materialize a checkpoint: $model_path" >&2
  exit 1
fi

bucket="${GCS_BUCKET%/}"
if [[ "$bucket" != gs://* ]]; then
  bucket="gs://$bucket"
fi
destination="$bucket/models/pretrained/$(basename "$model_path")"
gcloud storage cp "$model_path" "$destination"
echo "staged $model_path to $destination"
