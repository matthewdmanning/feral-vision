#!/usr/bin/env bash
# Register exactly one prepared Dataset; workflow scripts own its production.
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: scripts/data/register.sh DATASET_ROOT" >&2
    exit 2
fi

dataset_root="$(realpath -e -- "$1")"
repo_root="$(realpath -e -- "$(dvc root)")"
case "$dataset_root/" in
    "$repo_root/"?*) ;;
    *) echo "Dataset must be inside the DVC repository: $dataset_root" >&2; exit 1 ;;
esac

for directory in images annotations; do
    if [[ ! -d "$dataset_root/$directory" ]]; then
        echo "Dataset must contain $directory/: $dataset_root" >&2
        exit 1
    fi
done

cd "$repo_root"
dvc config core.remote >/dev/null
dvc add "$dataset_root"
dvc push "${dataset_root}.dvc"
