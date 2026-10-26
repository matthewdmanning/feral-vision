#!/usr/bin/env bash
set -euo pipefail

readonly repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  scripts/cloud/build_training_image.sh \
    --project PROJECT \
    --region REGION \
    --repository REPOSITORY \
    --image IMAGE \
    --tag TAG \
    --service-account SERVICE_ACCOUNT_EMAIL

Builds, verifies, and pushes the one canonical GPU training image. The final
line prints the digest-pinned Artifact Registry reference required by Terraform.

FIRST run scripts/cloud/check_training_image.sh. The image may already exist.
An image's age does not determine whether a build is needed.

Defaults come from cloud.env.local (see cloud.env.example); flags override them.
EOF
}

project="${GCP_PROJECT:-}"
region="${GCP_REGION:-}"
repository="${ARTIFACT_REPOSITORY:-}"
image="${TRAINING_IMAGE_NAME:-}"
tag=""
service_account="${BUILD_SERVICE_ACCOUNT:-}"

while (( "$#" )); do
  case "$1" in
    --project) project="${2:?--project requires a value}"; shift 2 ;;
    --region) region="${2:?--region requires a value}"; shift 2 ;;
    --repository) repository="${2:?--repository requires a value}"; shift 2 ;;
    --image) image="${2:?--image requires a value}"; shift 2 ;;
    --tag) tag="${2:?--tag requires a value}"; shift 2 ;;
    --service-account) service_account="${2:?--service-account requires a value}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for required in project region repository image tag service_account; do
  if [ -z "${!required}" ]; then
    echo "Missing required --${required//_/-}" >&2
    usage >&2
    exit 2
  fi
done

readonly image_ref="${region}-docker.pkg.dev/${project}/${repository}/${image}:${tag}"

checkpoint() {
  printf '[training-image] %-24s %s\n' "$1" "$2"
}

checkpoint "REMINDER" "did you run scripts/cloud/check_training_image.sh? The image may already exist."
checkpoint "LOCAL_TOOLING" "checking gcloud and active account"
command -v gcloud >/dev/null
active_account="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' | head -n1)"
test -n "$active_account"
checkpoint "LOCAL_TOOLING" "PASS account=${active_account}"

checkpoint "ARTIFACT_REGISTRY" "checking ${region}/${repository}"
gcloud artifacts repositories describe "$repository" \
  --location="$region" \
  --project="$project" \
  --format=json >/dev/null
checkpoint "ARTIFACT_REGISTRY" "PASS"

checkpoint "CLOUD_BUILD" "building ${image_ref}"
cd "$repository_root"
gcloud builds submit . \
  --project="$project" \
  --region="$region" \
  --quiet \
  --service-account="projects/${project}/serviceAccounts/${service_account}" \
  --config=feral-vision/deploy/cloudbuild.training-image.yaml \
  --substitutions="_TRAINING_IMAGE=${image_ref}"
checkpoint "CLOUD_BUILD" "PASS build, image check, and push completed"

checkpoint "IMAGE_DIGEST" "resolving pushed digest"
digest="$(gcloud artifacts docker images describe "$image_ref" \
  --project="$project" \
  --format='value(image_summary.digest)')"
if [[ ! "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]; then
  echo "Artifact Registry returned an invalid digest for ${image_ref}: ${digest}" >&2
  exit 1
fi
checkpoint "IMAGE_DIGEST" "PASS ${digest}"

printf '%s@%s\n' "${region}-docker.pkg.dev/${project}/${repository}/${image}" "$digest"
