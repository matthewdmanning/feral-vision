#!/usr/bin/env bash

load_training_parameters() {
  local provider="${BASH_SOURCE[0]%/*}/load_training_parameters.local.sh"
  if [[ ! -r "$provider" ]]; then
    echo "Missing local training-parameter provider: $provider" >&2
    return 1
  fi
  source "$provider"
  load_training_parameters_local
}
