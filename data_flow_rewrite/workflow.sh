#!/usr/bin/env bash
# The sole CLI. Python functions receive already parsed named arguments.
set -euo pipefail
export DVC_NO_ANALYTICS=1 DO_NOT_TRACK=1
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
fail() { printf '%s\n' "$1" >&2; exit 2; }
[[ $# -gt 0 ]] || fail 'Expected register, stage, or verify'
operation=$1
shift
case "$operation" in
  register) required='dataset id provenance workspace remote-url catalogue'; allowed="$required force new-catalogue" ;;
  stage) required='catalogue id destination remote-url'; allowed=$required ;;
  verify) required='staged'; allowed=$required ;;
  *) fail 'Unknown operation; expected register, stage, or verify' ;;
esac
declare -A values=()
while (( $# )); do
  flag=$1
  shift
  [[ $flag == --* ]] || fail 'Expected a named flag'
  key=${flag#--}
  attached=false
  if [[ $key == *=* ]]; then
    value=${key#*=}
    key=${key%%=*}
    attached=true
  fi
  [[ " $allowed " == *" $key "* ]] || fail 'Unknown flag for this operation'
  [[ ! -v values[$key] ]] || fail 'Duplicate flag'
  case "$key" in
    force|new-catalogue) [[ $attached == false ]] || fail 'Boolean flags take no value'
       values[$key]=true ;;
    *) if [[ $attached == true ]]; then
         [[ -n $value ]] || fail 'Missing flag value'
         values[$key]=$value
       else
         [[ $# -gt 0 && $1 != --* && -n $1 ]] || fail 'Missing flag value'
         values[$key]=$1; shift
       fi ;;

  esac
done
for key in $required; do
  [[ -v values[$key] ]] || fail "Missing --$key"
done
# Argument values stay argv data: never evaluate caller input as code.
args=("$operation")
for key in "${!values[@]}"; do args+=("$key" "${values[$key]}"); done
[[ -x $here/.venv/bin/python ]] || { printf '%s\n' 'Install the isolated environment with uv sync --project data_flow_rewrite --frozen' >&2; exit 1; }
exec "$here/.venv/bin/python" -I -c '
import sys
sys.path.insert(0, sys.argv[1])
from workflow import shell_call
operation = sys.argv[2]
arguments = dict(zip(sys.argv[3::2], sys.argv[4::2], strict=True))
arguments = {k.replace("-", "_"): v for k, v in arguments.items()}
if "id" in arguments:
    arguments["dataset_id"] = arguments.pop("id")
if "provenance" in arguments:
    arguments["provenance_path"] = arguments.pop("provenance")
for key in ("force", "new_catalogue"):
    if key in arguments:
        arguments[key] = arguments[key] == "true"
sys.exit(shell_call(operation, **arguments))
' "$here" "${args[@]}"
