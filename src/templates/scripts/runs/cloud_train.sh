#!/usr/bin/env bash
# Run inside the prepared container after the selected inputs have downloaded.
set -euo pipefail

: "${CONFIG_DIR:?Set the absolute directory containing the selected Hydra config}"
: "${CONFIG_NAME:?Set the selected Hydra config name}"
: "${RUN_OUTPUT_DIR:?Set the local directory containing all run outputs}"
: "${TRAINING_DATA_BUCKET_URI:?Set the existing Cloud Storage bucket URI}"
export PYTHONUNBUFFERED=1
export PYTHONPATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)${PYTHONPATH:+:$PYTHONPATH}"
export RUN_OUTPUT_DIR
mkdir -p "$RUN_OUTPUT_DIR"
cd "$RUN_OUTPUT_DIR"
export RUN_OUTPUT_DIR="$PWD"
export RUN_OUTPUT_URI
RUN_OUTPUT_URI=""

exec 3>&1 4>&2
exec > >(tee -a "$RUN_OUTPUT_DIR/console.log" >&3) 2>&1
log_pid=$!
watch_pid=""
train_pid=""

# Use this function to drain logs and verify exports before returning the training status.
finish() {
  local training_status="$?"
  trap - EXIT INT TERM
  if [[ -n "$watch_pid" ]]; then
    kill "$watch_pid" 2>/dev/null || true
    wait "$watch_pid" 2>/dev/null || true
  fi
  printf 'Training exit status: %s; exporting to %s\n' "$training_status" "$RUN_OUTPUT_URI"
  exec 1>&3 2>&4
  if ! wait "$log_pid"; then
    training_status=1
  fi
  if ! TRAINING_STATUS="$training_status" python -c 'import os; from run_outputs import finish_outputs; finish_outputs(os.environ["RUN_OUTPUT_DIR"], os.environ["RUN_OUTPUT_URI"], int(os.environ["TRAINING_STATUS"]))' 2>"$RUN_OUTPUT_DIR/export-errors.log"; then
    cat "$RUN_OUTPUT_DIR/export-errors.log" >&2
    echo "OUTPUT EXPORT FAILED: keep the VM and $RUN_OUTPUT_DIR for recovery." >&2
    exit 1
  fi
  cat "$RUN_OUTPUT_DIR/export-errors.log" >&2
  printf 'Outputs verified at %s\n' "$RUN_OUTPUT_URI"
  exit "$training_status"
}

# Use this function to stop training descendants before preserving interrupted outputs.
interrupt() {
  trap - INT TERM
  if [[ -n "$train_pid" ]]; then
    kill -TERM -- "-$train_pid" 2>/dev/null || true
    for _ in {1..20}; do
      if ! kill -0 "$train_pid" 2>/dev/null; then break; fi
      sleep 1
    done
    kill -KILL -- "-$train_pid" 2>/dev/null || true
    wait "$train_pid" 2>/dev/null || true
  fi
  exit 143
}

trap finish EXIT
trap interrupt INT TERM
RUN_OUTPUT_URI="$(python -c 'import os; from run_outputs import instance_output_uri; print(instance_output_uri(os.environ["TRAINING_DATA_BUCKET_URI"]))')"
printf 'Run outputs: %s\n' "$RUN_OUTPUT_URI"
# Verify storage access before training can produce irreplaceable outputs.
python -c 'import os; from run_outputs import publish_outputs; publish_outputs(os.environ["RUN_OUTPUT_DIR"], os.environ["RUN_OUTPUT_URI"])'
python -c 'import os; from run_outputs import watch_outputs; watch_outputs(os.environ["RUN_OUTPUT_DIR"], os.environ["RUN_OUTPUT_URI"])' &
watch_pid=$!
setsid python -c 'import os, sys; from run_outputs import train; train(os.environ["CONFIG_DIR"], os.environ["CONFIG_NAME"], os.environ["RUN_OUTPUT_DIR"], sys.argv[1:])' "$@" &
train_pid=$!
wait "$train_pid"
