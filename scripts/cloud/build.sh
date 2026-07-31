#!/usr/bin/env bash
set -euo pipefail

gcloud builds submit . \
  "--project=${GCP_PROJECT}" \
  --config=deploy/cloudbuild.build.yaml \
  "--substitutions=_REGION=${REGISTRY_REGION},_REPO=${ARTIFACT_REPOSITORY},_BASE_IMAGE_NAME=${BASE_IMAGE_NAME},_IMAGE_NAME=${TRAINING_IMAGE_NAME},_IMAGE_TAG=${IMAGE_TAG}"
