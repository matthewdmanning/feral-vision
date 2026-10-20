#!/usr/bin/env bash
# Create, document, bound, and clean all local acceptance state.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
project=$(cd -- "$here/.." && pwd)
trial_id=$(cat /proc/sys/kernel/random/uuid)
trial="$project/.dvc-rewrite-trial-$trial_id"
exclude="$project/.git/info/exclude"
[[ -f $exclude ]] || { printf '%s\n' 'Expected a normal checkout with .git/info/exclude' >&2; exit 2; }
mkdir "$trial"
printf '/.dvc-rewrite-trial-%s/\n' "$trial_id" >> "$exclude"
cat > "$trial/OPERATIONS.md" <<EOF
# DVC rewrite acceptance operations

UUID: $trial_id
Purpose: exercise real DVC registration, publication, recovery, and rejection.
Created by: bash dvc_vm_environ/tests/run.sh
Ignore: exact /.dvc-rewrite-trial-$trial_id/ entry in .git/info/exclude.
Commands: timeout 300 bash dvc_vm_environ/tests/acceptance.sh $trial
Optional audit: copy complete data/augmented, register, stage, verify, compare.
All fixtures, repositories, remotes, caches, logs, and hashes stay in this tree.
Cleanup trap verifies source hashes, removes this tree and its exact ignore line.
Results: dvc_vm_environ/VALIDATION.md (previous result replaced).
EOF
audit='Not run: data/augmented/ is absent from this checkout.'
cleanup() {
  result=$?
  trap - EXIT
  if [[ -f $trial/original.sha256 ]]; then
    if (cd "$project" && sha256sum -c "$trial/original.sha256") > "$trial/original-check.log" 2>&1; then
      audit="$audit Original source SHA-256 map verified unchanged."
    else
      audit="$audit Original source verification FAILED."
      result=1
    fi
  fi
  {
    printf '# Rewrite validation\n\n'
    printf 'Run: %s (UTC). Trial UUID: `%s`. Exit status: %s.\n\n' "$(date -u +'%Y-%m-%d %H:%M:%S')" "$trial_id" "$result"
    printf 'Environment: Python 3.12, DVC 3.67.1, dvc-data 3.18.2; isolated local filesystem remote.\n\n'
    printf '```text\n'
    [[ ! -f $trial/acceptance.log ]] || cat "$trial/acceptance.log"
    if [[ $result != 0 && -f $trial/last.stderr ]]; then
      cat "$trial/last.stderr"
    fi
    printf '```\n\nSupplied-data trial: %s\n\n' "$audit"
    printf 'No Python tests were written: required `write-python-test` skill is unavailable. The executable shell suite covers the public CLI with real DVC.\n\n'
    printf 'GCS authentication, regional deployment, producer/training/MLflow integration, and cross-machine concurrency were not tested.\n\n'
    printf 'Trial tree and its exact local ignore entry are removed on exit. No supplied source files are modified.\n'
  } > "$here/VALIDATION.md"
  # Match exactly; retain every unrelated local ignore entry.
  sed -i "\\|^/\\.dvc-rewrite-trial-$trial_id/\$|d" "$exclude"
  rm -rf -- "$trial"
  exit "$result"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
export TMPDIR="$trial/tmp" DVC_NO_ANALYTICS=1 DO_NOT_TRACK=1
mkdir "$TMPDIR"
if [[ -d $project/data/augmented ]]; then
  (cd "$project" && find data/augmented -type f -print0 | sort -z | xargs -0 -r sha256sum) > "$trial/original.sha256"
  cp -a "$project/data/augmented" "$trial/audit-copy"
fi
status=0
timeout 300 bash "$here/tests/acceptance.sh" "$trial" > "$trial/acceptance.log" 2>&1 || status=$?
cat "$trial/acceptance.log"
[[ $status == 0 ]] || exit "$status"
if [[ -d $trial/audit-copy ]]; then
  timeout 60 "$here/workflow.sh" register --dataset "$trial/audit-copy" --id supplied-augmented-audit --provenance "$trial/provenance.json" --workspace "$trial/audit-work" --remote-url "$trial/remote" --catalogue "$trial/audit.dvc" --new-catalogue > "$trial/audit-register.json" 2> "$trial/audit.stderr"
  rm -rf -- "$trial/audit-work"
  mkdir "$trial/audit-staged"
  cp -a "$trial/audit-copy" "$trial/audit-staged/dataset"
  timeout 60 "$here/workflow.sh" stage --catalogue "$trial/audit.dvc" --id supplied-augmented-audit --destination "$trial/audit-staged" --remote-url "$trial/remote" > "$trial/audit-stage.json" 2>> "$trial/audit.stderr"
  timeout 60 "$here/workflow.sh" verify --staged "$trial/audit-staged" > "$trial/audit-verify.json" 2>> "$trial/audit.stderr"
  diff -r -- "$trial/audit-copy" "$trial/audit-staged/dataset" > "$trial/audit-diff.log"
  audit='Full supplied-data copy registered, published, recovered without its workspace/cache, and verified; names and bytes matched. No mask pairings repaired.'
fi
