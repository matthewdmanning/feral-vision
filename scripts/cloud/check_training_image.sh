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
Exit 1: no image exists. Only now is a build justified.
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
  echo "[training-image-check] NO IMAGE FOUND under ${path}. A build is justified." >&2
  exit 1
fi

echo "$rows"
newest_package="$(printf '%s\n' "$rows" | head -n1 | awk -F' [|] ' '{print $1}')"
newest_digest="$(printf '%s\n' "$rows" | head -n1 | awk -F' [|] ' '{print $2}')"
echo "[training-image-check] IMAGE EXISTS."

# An image is current only if no input of the build changed after it was created.
newest_created="$(printf '%s\n' "$rows" | head -n1 | awk -F' [|] ' '{print $4}')"
last_input_change="$(git log -1 --format=%cI -- \
  deploy/Dockerfile.gcp deploy/cloudbuild.training-image.yaml \
  scripts/runs/container_train.sh src conf pyproject.toml uv.lock)"
echo "[training-image-check] newest image created : ${newest_created}"
echo "[training-image-check] last build-input commit: ${last_input_change}"
if [ "$(date -d "$last_input_change" +%s)" -gt "$(date -d "$newest_created" +%s)" ]; then
  echo "[training-image-check] STALE: build inputs changed after the newest image. Rebuild." >&2
  echo "[training-image-check] (Uncommitted changes are not covered. Run git status.)" >&2
else
  echo "[training-image-check] CURRENT: no committed build input changed since that image."
fi
printf '%s@%s\n' "$newest_package" "$newest_digest"
