#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/cloud/check_training_image.sh \
    --project PROJECT \
    --region REGION \
    --repository REPOSITORY \
    --image IMAGE

Read-only. Lists the pushes of one image in Artifact Registry, newest first.
Run it BEFORE you say that the training image is "not built", and BEFORE you
start a build. Artifact Registry is the only source of truth: an earlier agent
or session may have built the image already.

Exit 0: at least one image exists. The last line is the newest digest-pinned
        reference, ready for training_image in run.tfvars.
Exit 1: no image exists.
EOF
}

project=""
region=""
repository=""
image=""

while (( "$#" )); do
  case "$1" in
    --project) project="${2:?--project requires a value}"; shift 2 ;;
    --region) region="${2:?--region requires a value}"; shift 2 ;;
    --repository) repository="${2:?--repository requires a value}"; shift 2 ;;
    --image) image="${2:?--image requires a value}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for required in project region repository image; do
  if [ -z "${!required}" ]; then
    echo "Missing required --${required}" >&2
    usage >&2
    exit 2
  fi
done

path="${region}-docker.pkg.dev/${project}/${repository}/${image}"

echo "[training-image-check] listing ${path} (read-only)"
# package | digest | tags | created -- newest first.
rows="$(gcloud artifacts docker images list "$path" \
  --project="$project" \
  --include-tags \
  --sort-by=~CREATE_TIME \
  --format='csv[no-heading,separator=" | "](package,version,tags,createTime)')"

if [ -z "$rows" ]; then
  echo "[training-image-check] NO IMAGE FOUND under ${path}." >&2
  exit 1
fi

echo "$rows"
newest_package="$(printf '%s\n' "$rows" | head -n1 | awk -F' [|] ' '{print $1}')"
newest_digest="$(printf '%s\n' "$rows" | head -n1 | awk -F' [|] ' '{print $2}')"
echo "[training-image-check] IMAGE EXISTS."

printf '%s@%s\n' "$newest_package" "$newest_digest"
