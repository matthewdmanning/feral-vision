#!/usr/bin/env bash
# Shell behavior tests; no Python test framework or legacy project code.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
root=${1:?Supply an operation-owned project-root trial directory}
[[ -f $root/OPERATIONS.md && $root == /* ]] || exit 2
export TMPDIR="$root/tmp" DVC_NO_ANALYTICS=1 DO_NOT_TRACK=1
mkdir -p "$TMPDIR" "$root/source/images" "$root/source/masks" "$root/remote"
# Portable 2x2 image fixtures: registration treats all contents as opaque bytes.
printf 'P2\n2 2\n255\n0 127\n255 64\n' > "$root/source/images/original.pgm"
printf 'P2\n2 2\n1\n0 1\n1 0\n' > "$root/source/masks/original.pgm"
cp "$root/source/masks/original.pgm" "$root/source/masks/brightness.pgm"
printf 'P2\n2 2\n255\n10 137\n255 74\n' > "$root/source/images/brightness.pgm"
(cd "$root/source" && find . -type f -print0 | sort -z | xargs -0 sha256sum) > "$root/source.sha256"
printf '%s\n' '{"origin":"acquired","source_refs":["retained-store:fixture/v1"]}' > "$root/provenance.json"
flow=("$here/workflow.sh")
count=0
pass() { count=$((count+1)); printf 'PASS %02d %s\n' "$count" "$1"; }
run() { timeout 60 "${flow[@]}" "$@" > "$root/result.json" 2> "$root/last.stderr"; jq -e 'type == "object"' "$root/result.json" >/dev/null; }
reject() {
  local expected=$1
  shift
  local actual=0
  timeout 60 "${flow[@]}" "$@" > "$root/rejected.stdout" 2> "$root/last.stderr" || actual=$?
  [[ $actual == "$expected" && ! -s $root/rejected.stdout ]] || { cat "$root/last.stderr" >&2; printf 'Unexpected rejection status %s (wanted %s)\n' "$actual" "$expected" >&2; exit 1; }
}
register=(register --dataset "$root/source" --provenance "$root/provenance.json" --workspace "$root/work" --remote-url "$root/remote" --catalogue "$root/bootstrap.dvc")
run "${register[@]}" --id 'dataset/α' --new-catalogue
hash=$(jq -r .dataset_hash "$root/result.json")
cp "$root/bootstrap.dvc" "$root/first.dvc"
pass 'first native registration, metadata archive publication, and JSON result'
run stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/staged" --remote-url "$root/remote"
cmp "$root/source/images/original.pgm" "$root/staged/payload/images/original.pgm"
[[ $(jq -r .dataset_hash "$root/result.json") == "$hash" ]]
cp "$root/staged/payload.dvc" "$root/original-record.dvc"
cp "$root/staged/payload.dir" "$root/original-index.dir"
jq -e 'length == 4 and ([.[].relpath] | index("masks/brightness.pgm") != null)' "$root/staged/payload.dir" >/dev/null
pass 'native index preserves repeated bytes under distinct filenames'
reject 2 "${register[@]}" --id 'dataset/α'
run "${register[@]}" --id 'dataset/α' --force
cmp "$root/bootstrap.dvc" "$root/first.dvc"
pass 'identical-ID retry needs force and preserves exact deterministic snapshot'
reject 2 "${register[@]}" --id second
run "${register[@]}" --id second --force
pass 'same complete Dataset hash requires force for a distinct identity'
printf '%s\n' '{"source_refs":["retained-store:fixture/v1"],"origin":"acquired"}' > "$root/provenance.json"
run "${register[@]}" --id 'dataset/α' --force
pass 'provenance object ordering does not alter identity'
cp "$root/bootstrap.dvc" "$root/before-reject.dvc"
printf '%s\n' '{"origin":"derived","source_refs":["retained-store:fixture/v1"],"lineage_ref":"catalogue:parent-and-operations"}' > "$root/provenance.json"
reject 2 "${register[@]}" --id 'dataset/α' --force
cmp "$root/bootstrap.dvc" "$root/before-reject.dvc"
pass 'changed provenance cannot replace an ID even with force'
run "${register[@]}" --id derived --force
run stage --catalogue "$root/bootstrap.dvc" --id derived --destination "$root/derived" --remote-url "$root/remote"
[[ $(sed -n '/origin:/p' "$root/derived/payload.dvc") == *derived* ]]
pass 'derived lineage is retained in the original DVC record'
printf '%s\n' '{"origin":"inference","source_refs":["retained-store:inference"],"model_ref":"model-catalogue:version-123"}' > "$root/provenance.json"
run "${register[@]}" --id inference --force
pass 'inference model catalogue reference is accepted and retained'
printf '%s\n' '{"origin":"acquired","source_refs":["retained-store:fixture/v1"]}' > "$root/provenance.json"
printf extra > "$root/source/extra.bin"
reject 2 "${register[@]}" --id 'dataset/α' --force
run "${register[@]}" --id unrelated
rm "$root/source/extra.bin"
pass 'changed bytes cannot replace an ID; a different payload can register separately'
# Retain only the bootstrap and remote, deleting all registration repositories/caches.
rm -rf "$root/work" "$root/staged" "$root/derived"
run stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/recovered" --remote-url "$root/remote"
cmp "$root/recovered/payload.dvc" "$root/original-record.dvc"
cmp "$root/recovered/payload.dir" "$root/original-index.dir"
[[ ! -e $root/recovered/payload/extra.bin ]]
pass 'cache-free recovery selects one payload from a multi-Dataset catalogue'
# Remove the unrelated-only remote object: selection must still succeed.
unrelated_hash=$(printf extra | md5sum | cut -d' ' -f1)
unrelated_path="$root/remote/files/md5/${unrelated_hash:0:2}/${unrelated_hash:2}"
mv "$unrelated_path" "$root/held-unrelated"
run stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/selected-only" --remote-url "$root/remote"
mv "$root/held-unrelated" "$unrelated_path"
run stage --catalogue "$root/bootstrap.dvc" --id unrelated --destination "$root/unrelated" --remote-url "$root/remote"
cp "$root/unrelated/payload.dvc" "$root/recovered/payload.dvc"
reject 1 verify --staged "$root/recovered"
cp "$root/original-record.dvc" "$root/recovered/payload.dvc"
pass 'selected staging ignores missing unrelated objects; an unrelated record fails verification'
# Verify that no unrelated payload object was retrieved (the handoff has no cache).
[[ $(find "$root/recovered" -type f | wc -l) == 6 ]]
mv "$root/recovered" "$root/moved"
run verify --staged "$root/moved"
pass 'portable handoff verifies after being moved'
cp "$root/moved/payload/images/original.pgm" "$root/saved-image"
printf broken > "$root/moved/payload/images/original.pgm"
reject 1 verify --staged "$root/moved"
cp "$root/saved-image" "$root/moved/payload/images/original.pgm"
cp "$root/moved/payload/masks/original.pgm" "$root/saved-mask"
printf broken > "$root/moved/payload/masks/original.pgm"
reject 1 verify --staged "$root/moved"
cp "$root/saved-mask" "$root/moved/payload/masks/original.pgm"
pass 'changed image and mask are rejected'
mv "$root/moved/payload/images/original.pgm" "$root/removed"
reject 1 verify --staged "$root/moved"
mv "$root/removed" "$root/moved/payload/images/original.pgm"
printf extra > "$root/moved/payload/extra"
reject 1 verify --staged "$root/moved"
rm "$root/moved/payload/extra"
mv "$root/moved/payload/images/original.pgm" "$root/moved/payload/images/renamed.pgm"
reject 1 verify --staged "$root/moved"
mv "$root/moved/payload/images/renamed.pgm" "$root/moved/payload/images/original.pgm"
pass 'missing, extra, and renamed files are rejected'
printf ' ' >> "$root/moved/payload.dir"
reject 1 verify --staged "$root/moved"
cp "$root/original-index.dir" "$root/moved/payload.dir"
sed 's/path: payload/path: ..\/escape/' "$root/original-record.dvc" > "$root/moved/payload.dvc"
reject 2 verify --staged "$root/moved"
cmp "$root/moved/payload.dvc" <(sed 's/path: payload/path: ..\/escape/' "$root/original-record.dvc")
cp "$root/original-record.dvc" "$root/moved/payload.dvc"
pass 'damaged native index and escaping records fail without rewriting evidence'
ln -s "$root/saved-image" "$root/moved/payload/link"
reject 2 verify --staged "$root/moved"
rm "$root/moved/payload/link"
mkfifo "$root/moved/payload/pipe"
reject 2 verify --staged "$root/moved"
rm "$root/moved/payload/pipe"
printf ignored > "$root/moved/payload/.dvcignore"
reject 2 verify --staged "$root/moved"
rm "$root/moved/payload/.dvcignore"
pass 'symlinks, special files, and ignore controls cannot hide payload contents'
reject 2 stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/moved" --remote-url "$root/remote"
run verify --staged "$root/moved"
pass 'nonempty staging destination is preserved'
for bad in '{"origin":"inference","source_refs":["retained:source"]}' '{"origin":"derived","source_refs":["retained:source"]}' '{"origin":"acquired","source_refs":[]}' '{"origin":"acquired","source_refs":["/worker/input"]}' '{"origin":"acquired","source_refs":["retained:source"],"typo":true}' '{"origin":"acquired","origin":"derived","source_refs":["retained:source"]}'; do
  printf '%s\n' "$bad" > "$root/provenance.json"
  reject 2 "${register[@]}" --id bad
 done
pass 'missing model/lineage, malformed references, unknown fields, and duplicate JSON keys are rejected'
reject 2 verify --staged "$root/moved" --unknown value
reject 2 verify --staged "$root/moved" --staged "$root/moved"
reject 2 verify --staged
reject 2 unknown
reject 2 "${register[@]}" --id new --new-catalogue
pass 'shell rejects unknown operations, flags, duplicate and missing values'
cp "$root/bootstrap.dvc" "$root/unsafe.dvc"
printf '\nwdir: ../escape\n' >> "$root/unsafe.dvc"
reject 2 stage --catalogue "$root/unsafe.dvc" --id 'dataset/α' --destination "$root/unsafe-stage" --remote-url "$root/remote"
[[ ! -e $root/unsafe-stage && ! -e $root/escape ]]
pass 'escaping bootstrap descriptor is rejected before materialization'
printf '%s\n' '{"origin":"acquired","source_refs":["retained-store:fixture/v1"]}' > "$root/provenance.json"
mkdir -p "$root/locked-work"
(exec 9> "$root/locked-work/writer.lock"; flock -n 9; reject 2 register --dataset "$root/source" --id locked --provenance "$root/provenance.json" --workspace "$root/locked-work" --remote-url "$root/remote" --catalogue "$root/locked.dvc" --new-catalogue)
pass 'simultaneous local writer fails without publication'
printf not-a-directory > "$root/broken-remote"
reject 1 register --dataset "$root/source" --id failure --provenance "$root/provenance.json" --workspace "$root/failure-work" --remote-url "$root/broken-remote" --catalogue "$root/failure.dvc" --new-catalogue
[[ ! -e $root/failure.dvc ]]
pass 'push failure produces no success JSON or bootstrap descriptor'
# Make bootstrap installation fail after payload and archive pushes, then retry.
printf blocked > "$root/blocked-parent"
reject 1 register --dataset "$root/source" --id retry --provenance "$root/provenance.json" --workspace "$root/retry-work" --remote-url "$root/remote" --catalogue "$root/blocked-parent/retry.dvc" --new-catalogue
rm "$root/blocked-parent"
run register --dataset "$root/source" --id retry --provenance "$root/provenance.json" --workspace "$root/retry-work" --remote-url "$root/remote" --catalogue "$root/blocked-parent/retry.dvc" --new-catalogue
pass 'retry after partially completed publication recovers'
# Removing an actually referenced object must fail restoration without changing dest.
object_hash=$(jq -r '.[0].md5' "$root/original-index.dir")
object_path="$root/remote/files/md5/${object_hash:0:2}/${object_hash:2}"
mv "$object_path" "$root/held-object"
mkdir "$root/empty-dest"
reject 1 stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/empty-dest" --remote-url "$root/remote"
[[ -d $root/empty-dest && -z $(ls -A "$root/empty-dest") ]]
mv "$root/held-object" "$object_path"
pass 'missing remote cache object stops staging and preserves empty destination'
(cd "$root/source" && sha256sum -c "$root/source.sha256") > "$root/source-check.log"
run verify --staged "$root/moved"
pass 'original synthetic source unchanged; final handoff still verifies'
# Fail only the metadata-archive push after payload publication.
cp "$root/bootstrap.dvc" "$root/shadow.dvc"
run register --dataset "$root/source" --id metadata-failure --provenance "$root/provenance.json" --workspace "$root/shadow-work" --remote-url "$root/remote" --catalogue "$root/shadow.dvc" --force
archive_hash=$(sed -n 's/^- md5: //p' "$root/shadow.dvc")
archive_object="$root/remote/files/md5/${archive_hash:0:2}/${archive_hash:2}"
mv "$archive_object" "$root/held-archive"
mkdir "$archive_object"
printf blocked > "$archive_object/blocker"
cp "$root/bootstrap.dvc" "$root/pre-upload.dvc"
reject 1 register --dataset "$root/source" --id metadata-failure --provenance "$root/provenance.json" --workspace "$root/metadata-work" --remote-url "$root/remote" --catalogue "$root/bootstrap.dvc" --force
cmp "$root/bootstrap.dvc" "$root/pre-upload.dvc"
rm -rf "$archive_object"
mv "$root/held-archive" "$archive_object"
run register --dataset "$root/source" --id metadata-failure --provenance "$root/provenance.json" --workspace "$root/metadata-work" --remote-url "$root/remote" --catalogue "$root/bootstrap.dvc" --force
pass 'metadata upload failure preserves the prior bootstrap and can be retried'
# Real DVC publishes deliberately unsafe metadata fixtures; the production
# shell interface must reject them before extracting any archive member.
mkdir "$root/evil-repo" "$root/evil-input"
printf harmless > "$root/evil-input/file"
(
  cd "$root/evil-repo"
  export DVC_SYSTEM_CONFIG_DIR="$root/evil-system" DVC_GLOBAL_CONFIG_DIR="$root/evil-global" DVC_SITE_CACHE_DIR="$root/evil-cache"
  timeout 30 "$here/.venv/bin/dvc" init --no-scm > "$root/evil.log" 2>&1
  timeout 30 "$here/.venv/bin/dvc" config cache.type copy >> "$root/evil.log" 2>&1
  timeout 30 "$here/.venv/bin/dvc" remote add -d storage "$root/remote" >> "$root/evil.log" 2>&1
  tar -cf catalogue.tar --transform='s|file|../escaped|' -C "$root/evil-input" file
  timeout 30 "$here/.venv/bin/dvc" add catalogue.tar >> "$root/evil.log" 2>&1
  timeout 30 "$here/.venv/bin/dvc" push catalogue.tar.dvc >> "$root/evil.log" 2>&1
)
reject 2 stage --catalogue "$root/evil-repo/catalogue.tar.dvc" --id malicious --destination "$root/unsafe-tar" --remote-url "$root/remote"
[[ ! -e $root/unsafe-tar && ! -e $root/escaped ]]
pass 'traversal archive published through real DVC is rejected before extraction'
# Reuse a small real-DVC metadata publishing fixture for link/duplicate/absolute cases.
for unsafe in symlink duplicate absolute malformed; do
  (
    cd "$root/evil-repo"
    export DVC_SYSTEM_CONFIG_DIR="$root/evil-system" DVC_GLOBAL_CONFIG_DIR="$root/evil-global" DVC_SITE_CACHE_DIR="$root/evil-cache"
    case "$unsafe" in
      symlink) ln -sf "$root/saved-image" "$root/evil-input/link"; tar -cf catalogue.tar -C "$root/evil-input" link ;;
      duplicate) tar -cf catalogue.tar -C "$root/evil-input" file file ;;
      absolute) tar -cf catalogue.tar --transform='s|file|/absolute-escape|' -C "$root/evil-input" file ;;
      malformed) mkdir -p "$root/evil-input/$(printf '%064d' 0)"; printf invalid > "$root/evil-input/$(printf '%064d' 0)/payload.dvc"; tar -cf catalogue.tar -C "$root/evil-input" "$(printf '%064d' 0)/payload.dvc" ;;
    esac
    timeout 30 "$here/.venv/bin/dvc" add catalogue.tar >> "$root/evil.log" 2>&1
    timeout 30 "$here/.venv/bin/dvc" push catalogue.tar.dvc >> "$root/evil.log" 2>&1
  )
  reject 2 stage --catalogue "$root/evil-repo/catalogue.tar.dvc" --id malicious --destination "$root/unsafe-tar" --remote-url "$root/remote"
  [[ ! -e $root/unsafe-tar ]]
done
pass 'symlink, duplicate, absolute, and malformed metadata archives are rejected'
# Relative arguments retain the caller directory; opaque IDs need not be paths.
(
  cd "$root"
  printf 'invalid module fixture; must never be imported\n' > workflow.py
  run register --dataset source --id=--opaque-id --provenance provenance.json --workspace relative-work --remote-url "$root/remote" --catalogue relative.dvc --new-catalogue
  run stage --catalogue relative.dvc --id=--opaque-id --destination relative-staged --remote-url "$root/remote"
  run verify --staged relative-staged
)
pass 'relative input paths and opaque flag-like IDs round-trip'
mkdir "$root/empty-source"
reject 2 register --dataset "$root/empty-source" --id empty --provenance "$root/provenance.json" --workspace "$root/rejected-work" --remote-url "$root/remote" --catalogue "$root/rejected.dvc" --new-catalogue
ln -s "$root/saved-image" "$root/source/link"
reject 2 register --dataset "$root/source" --id linked --provenance "$root/provenance.json" --workspace "$root/rejected-work" --remote-url "$root/remote" --catalogue "$root/rejected.dvc" --new-catalogue
rm "$root/source/link"
reject 2 register --dataset "$root/source" --id missing --provenance "$root/provenance.json" --workspace "$root/rejected-work" --remote-url "$root/remote" --catalogue "$root/absent.dvc"
reject 2 stage --catalogue "$root/bootstrap.dvc" --id absent-id --destination "$root/absent-stage" --remote-url "$root/remote"
pass 'empty and linked source trees, lost bootstrap, and unknown IDs fail safely'
run stage --catalogue "$root/first.dvc" --id 'dataset/α' --destination "$root/old-snapshot" --remote-url "$root/remote"
run verify --staged "$root/old-snapshot"
pass 'earlier immutable bootstrap remains recoverable after catalogue extension'
# Restoring an empty destination succeeds too.
mkdir "$root/success-empty"
run stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/success-empty" --remote-url "$root/remote"
pass 'verified staging atomically replaces an empty destination'
(cd "$root/source" && sha256sum -c "$root/source.sha256") > "$root/source-check.log"
# Changing bytes while preserving size and mtime must not bypass fresh hashing.
cp -p "$root/moved/payload/images/original.pgm" "$root/mtime-original"
sed 's/127/128/' "$root/mtime-original" > "$root/moved/payload/images/original.pgm"
touch -r "$root/mtime-original" "$root/moved/payload/images/original.pgm"
reject 1 verify --staged "$root/moved"
cp -p "$root/mtime-original" "$root/moved/payload/images/original.pgm"
pass 'fresh DVC hashing detects changed bytes despite identical size and mtime'
# An operation must never publish cache files into its caller source tree.
reject 2 register --dataset "$root/source" --id overlap --provenance "$root/provenance.json" --workspace "$root/overlap-work" --remote-url "$root/source/nested-remote" --catalogue "$root/overlap.dvc" --new-catalogue
[[ ! -e $root/source/nested-remote ]]
pass 'local remote overlapping the source is rejected without modifying the source'
# The validated retained index, not unchecked remote index paths, drives staging.
index_object="$root/remote/files/md5/${hash:0:2}/${hash:2}"
cp "$index_object" "$root/saved-remote-index"
chmod u+w "$index_object"
printf '[{"md5":"%s","relpath":"../escaped"}]' "$object_hash" > "$index_object"
run stage --catalogue "$root/bootstrap.dvc" --id 'dataset/α' --destination "$root/safe-index-stage" --remote-url "$root/remote"
[[ ! -e $root/escaped ]]
cmp "$root/original-index.dir" "$root/safe-index-stage/payload.dir"
cp "$root/saved-remote-index" "$index_object"
chmod a-w "$index_object"
pass 'validated retained index prevents unsafe remote index paths from controlling retrieval'
(cd "$root/source" && sha256sum -c "$root/source.sha256") > "$root/source-check.log"
printf 'Completed %d behavioral checks\n' "$count"
