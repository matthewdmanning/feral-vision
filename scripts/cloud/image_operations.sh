#!/usr/bin/env bash
set -euo pipefail

readonly repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"


# Use this function to read one deployment substitution from the selected YAML file.
read_deployment_substitution() {
  local deployment_config_file="$1"
  local substitution_name="$2"

  awk -F ': *' -v name="$substitution_name" '
    $1 ~ "^[[:space:]]*" name "[[:space:]]*$" {
      print $2
      found = 1
      exit
    }
    END { exit !found }
  ' "$deployment_config_file"
}


deployment_config_file="$repository_root/deploy/cloudbuild.yaml"
while (( "$#" )); do
  case "$1" in
    --config)
      deployment_config_file="${2:?--config requires a deployment configuration file}"
      shift 2
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

gcp_project_id="$(read_deployment_substitution "$deployment_config_file" _GCP_PROJECT)"
artifact_registry_region="$(read_deployment_substitution "$deployment_config_file" _REGION)"
artifact_registry_repository="$(read_deployment_substitution "$deployment_config_file" _REPO)"
base_image_name="$(read_deployment_substitution "$deployment_config_file" _BASE_IMAGE_NAME)"
training_image_name="$(read_deployment_substitution "$deployment_config_file" _IMAGE_NAME)"
image_tag="$(read_deployment_substitution "$deployment_config_file" _IMAGE_TAG)"

cd "$repository_root"
gcloud builds submit . \
  "--project=${gcp_project_id}" \
  "--region=${artifact_registry_region}" \
  --quiet \
  --config=deploy/cloudbuild.build.yaml \
  "--substitutions=_REGION=${artifact_registry_region},_REPO=${artifact_registry_repository},_BASE_IMAGE_NAME=${base_image_name},_IMAGE_NAME=${training_image_name},_IMAGE_TAG=${image_tag}"
