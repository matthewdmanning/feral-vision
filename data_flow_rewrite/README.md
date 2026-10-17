# Independent DVC data workflow

This fresh implementation registers caller-prepared files, publishes them and
an immutable catalogue snapshot through DVC, and restores a selected Dataset
with its original record and native file index. It imports no existing project
code and changes no legacy workflow. The implementation plan alongside this
README defines its scope; the prior data flow remains separate.

## Environment and entrypoint

Use Linux, Bash 4.3+, Python 3.12, and `uv`. Install the isolated, locked
environment from the repository root:

```bash
uv sync --project data_flow_rewrite --frozen
```

DVC with GCS support is pinned to 3.67.1 and `dvc-data` to 3.18.2. DVC's
published requirement is `dvc-data>=3.18.2,<3.19.0`. PyYAML is a direct, pinned
dependency. No root environment or project dependencies are used.

`workflow.sh` is the only CLI; `workflow.py` contains Python functions without a
CLI or subprocess-based DVC wrappers. Paths supplied to the shell are relative
to the caller's current directory. Every operation emits exactly one JSON
object to stdout on success. Diagnostics go to stderr. Exit codes are 0 for
success, 2 for invalid input or policy rejection, and 1 for operational or
verification failure. Failed operations emit no stdout result.

| Operation | Required flags | Optional flags |
| --- | --- | --- |
| `register` | `--dataset`, `--id`, `--provenance`, `--workspace`, `--remote-url`, `--catalogue` | `--force`, `--new-catalogue` |
| `stage` | `--catalogue`, `--id`, `--destination`, `--remote-url` | None |
| `verify` | `--staged` | None |

Flags must be unique. Values starting with `--` can use `--id=--opaque-id` syntax. No positional arguments, unknown flags, or implicit
catalogue creation are accepted. Use an absolute filesystem remote path for
local operation, or a non-secret `gs://bucket/prefix` locator. URL credentials,
queries, and fragments are rejected. GCS authentication uses the normal external
DVC/GCS credential mechanism; this package does not discover credentials,
configure cloud infrastructure, or run cloud CLIs. DVC system/global/project
configuration is isolated from each new no-SCM repository. Cache links are
copies. Python functions change process-level DVC configuration selectors while
running; call them serially or use separate processes.

## Caller identity and provenance

An ID is a nonempty, opaque UTF-8 string, mapped to a SHA-256 directory name.
Its original value remains in the DVC record. A registration's native DVC MD5
`.dir` hash identifies filenames and contents, independently of the caller ID.
MD5 is content identity and accidental-change detection, not adversarial proof
of authenticity or source history.

The provenance input is a JSON object with these fields:

```json
{
  "origin": "derived",
  "source_refs": ["retained-source-catalogue:source-123"],
  "lineage_ref": "retained-lineage-catalogue:parent-and-per-item-changes"
}
```

`origin` is `acquired`, `derived`, or `inference`. `source_refs` must contain at
least one nonempty retained source reference. `derived` requires `lineage_ref`;
`inference` requires `model_ref`, naming a model in the caller's existing model
catalogue. Either optional reference may appear on any origin. Unknown fields,
duplicate JSON keys, empty references, and explicit worker-local/file paths are
rejected. Reference strings are preserved exactly. References are validated
structurally; callers remain responsible for retention and resolvability.
Version 1, ID, and provenance live in the `.dvc` record's top-level `meta`.

| Registration state in the supplied snapshot | Behavior |
| --- | --- |
| New ID and new complete Dataset hash | Register |
| New ID and matching complete Dataset hash | Report matching IDs and reject; `--force` registers a distinct identity |
| Existing ID, same contents and parsed provenance | Reject; `--force` preserves the exact record and retries publication |
| Existing ID, changed contents or provenance | Reject even with `--force` |

JSON object formatting/key order does not affect provenance equality. Repeated
bytes under distinct filenames remain distinct native index entries. Duplicate
checks compare entire Dataset hashes, within the supplied catalogue snapshot.
Independently forked snapshots and other remotes are outside that scope.

## Files and publication

The source must be finished before registration. Registration copies every
regular file with its relative name; it does not infer image/mask pairings,
rename annotations, enforce `images/annotations`, or invent augmentation
history. The audit's `images/masks` layout is supported. Empty datasets,
symlinks, special files, Git/DVC control files, and unsafe/nonportable paths are
rejected before hashing. Empty directories are not tracked by DVC. Source data
must remain separate from the managed workspace and bootstrap descriptor. A local
remote must also be separate from the source and managed workspace.

A local workspace contains `registrations/` with isolated per-ID repositories,
`catalogues/` with tracked metadata archives, `snapshots/` with immutable
bootstrap descriptors, and a `writer.lock`. One writer at a time holds a local
nonblocking lock. Operation-owned temporary directories are cleaned on failure.
There is no distributed locking or latest-pointer service; callers must supply
the current descriptor and coordinate writers across workspaces/machines.

Each registration uses exactly one `dataset.dvc` record and native `.dir`
index. Catalogue archives contain only those original record/index pairs under
safe ID directories. Tar names, member order, permissions, ownership, and times
are normalized. Identical metadata yields identical archive bytes. Datasets,
credentials, local DVC settings, caches, and logs are excluded.

Publication pushes only the selected Dataset, then a separately tracked
`catalogue.tar` containing all known metadata. It checks targeted remote status
and explicit existence of every selected cache object, including directory
indexes, before publishing the bootstrap pointer. A successful push exit alone
is insufficient. Only after both outputs are available does an atomic rename
install `--catalogue`. Earlier snapshot descriptors and remote objects are
retained. There is no remote garbage collection or automatic deletion.

`--catalogue` must exist unless `--new-catalogue` explicitly requests an empty
catalogue and requires an absent descriptor. Losing a descriptor never silently
starts a new catalogue. Keep the returned descriptor and non-secret remote
locator **outside ephemeral workers**. An arbitrary caller ID alone cannot
recover a lost catalogue pointer.

## Recovery and consumer handoff

Stage using the retained bootstrap descriptor, remote locator, caller ID, and
an absent or empty destination. The workflow downloads and validates catalogue
metadata, then retrieves only the selected dataset. Bootstrap descriptors,
archive members, ID associations, metadata fields, and native index paths are
validated before they can control materialization. The validated retained index
is seeded into the retrieval cache before DVC loads dataset paths.

The completed layout is:

```text
destination/
  dataset/
  dataset.dvc
  dataset.dir
```

The record and index retain their registered bytes. `dataset.dvc` references
the sibling `dataset/`. `dataset.dir` is outside the dataset to avoid
self-inclusion. No credentials, retrieval repository, cache, or symlinks are
needed after staging. Move the entire directory freely.

Verification checks the record schema/provenance, hashes exact index bytes
using pinned DVC hashing, validates individual index membership, then builds a
fresh native DVC directory tree with no saved hash state or ignore rules. Names,
bytes, size, and file count must match. A changed image/mask, missing/extra or
renamed file, damaged index, or unrelated record fails without rewriting
expected evidence. Staging verifies in a sibling temporary directory before
atomically installing the handoff. A nonempty destination is preserved.

Returned JSON names `id`, `dataset_hash`, `dataset`, `record`, and `index` for
stage/verify; registration returns `id`, `dataset_hash`, `catalogue`, and
`remote_url`. A future consumer must load that verified dataset unchanged and
retain its accompanying record in its Run Record. This package does not invoke
training or MLflow, and verification does not prove future consumer behavior.

## Failure recovery

On failure, retain the previous bootstrap pointer. Fix remote access or missing
objects and retry with the same source, ID, provenance, and current catalogue.
Use `--force` when that catalogue already contains the identical ID. A failed
first publication with no descriptor can be retried with `--new-catalogue`.
Uploaded but unreferenced objects may remain; do not delete them automatically.
Local repositories from interrupted publication do not establish publication;
the installed bootstrap descriptor is authoritative.

Restoring after worker loss requires only the retained bootstrap descriptor,
remote locator, remote objects, and external credentials. All selected dataset
objects and its native index must remain in the remote. Metadata recovery does
not restore unrelated datasets.

## Validation and limits

Run the complete local acceptance suite from the repository root:

```bash
timeout 420 bash data_flow_rewrite/tests/run.sh
```

The runner uses Bash, `jq`, GNU coreutils/tar, and real local DVC storage. It
creates a UUID project-root trial tree and operations document, adds a precise
local ignore entry, bounds commands, checks source hashes, and cleans both the
tree and ignore entry on exit. If `data/augmented/` exists, it copies the complete
source and additionally exercises its registration, publication, cache-free
recovery, and verification without repairing missing-mask observations.
Otherwise it explicitly records that the supplied-data trial was unavailable.
Synthetic tests use small 2D PGM fixtures with duplicate mask contents.

See [VALIDATION.md](VALIDATION.md) for actual results. The required
`write-python-test` skill is not installed in this checkout/session; therefore
no Python tests were written or reviewed. The behavioral suite lives in
`tests/acceptance.sh` instead of the planned `tests/test_workflow.py`.

The guide-impact check is complete: this independent opt-in workflow is
documented here, under the user-required rewrite directory; existing production
operator guides and source remain unchanged. Local tests prove DVC mechanics,
not GCS credentials, regional placement, or downstream training readiness.

**Follow-up: Implement Git backup of the DVC catalogue metadata and retained
bootstrap descriptors. The user confirmed it will be used.** The runtime
workflow performs no Git operations. Producer integration, training/MLflow,
cloud provisioning, remote garbage collection, distributed catalogue concurrency,
and migration/repair of the previous implementation remain outside this rewrite.
