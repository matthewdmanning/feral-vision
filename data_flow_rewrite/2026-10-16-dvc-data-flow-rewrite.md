# Fresh DVC data workflow: implementation plan

Status: implementation plan, 2026-10-16. No implementation or execution is
claimed by this document.

## 1. Authority and purpose

Build a fresh implementation. The previous implementation is not a starting
point to repair, refactor, wrap, or reproduce.

The requirements sources are:

- [User requirements and lifecycle](../docs/data_flow_audit/instructions.md).
- [Data flow reference](../docs/data_flow_audit/data_flow_reference.md), subject
  to the authoritative user requirements.
- [DVC command evidence and association diagnosis](../docs/data_flow_audit/dvc_commands.md).
- [MLflow findings](../docs/data_flow_audit/mlflow_dvc_findings.md), only for the
  documented downstream boundary; implementing MLflow is excluded.
- The user's subsequent decisions, recorded below.

Do not derive requirements, interfaces, schemas, or architecture from existing
implementation files or other repository documents. Do not read existing
training operations, cloud scripts, Terraform, MLflow scripts, or unrelated
Hydra files. Do not delegate an implementation review of those files. If a
specific external contract becomes necessary, a Luna subagent may extract only
that requested contract; its implementation and architecture are not design
inputs. No such extraction is needed for the workflow specified here.

Official DVC specifications and versioned source establish tool mechanics, not
project requirements. Do not adopt cookbook workflows or introduce DVC training
orchestration.

### Decisions already made by the user

- All new implementation, tests, configuration, and documentation belong under
  `data_flow_rewrite/`.
- Scope is DVC operations. Scripts may execute in a cloud environment. Google
  Cloud commands such as `gcloud`, infrastructure, training operations, MLflow
  scripts, and unrelated Hydra files are excluded.
- Accept caller-supplied source and lineage references. Do not integrate the
  acquisition, augmentation, or inference producers.
- Use a caller-supplied Dataset ID. IDs remain immutable.
- An exact Dataset content-hash match requires an explicit `--force` flag to
  complete registration. This flag never permits replacing an ID's contents
  or lineage.
- Publish metadata bundles through DVC. Git backup will be used later and must
  be recorded as follow-up work.
- PR creation, commits, pushes, merges, branching, and other Git operations are
  outside the current task. They are not prerequisites for this document or
  steps in the implementation workflow.

## 2. Outcome and boundaries

Implement this DVC-side lifecycle:

1. Receive prepared data and retained provenance references from a caller.
2. Register a unique Dataset identity and its contents.
3. Publish the Dataset contents and required catalogue metadata through DVC.
4. Restore a selected Dataset to a new local destination, including on
   ephemeral GCE, with its original DVC record and file index.
5. Verify that the staged filenames and contents match the selected record.
6. Return the verified dataset path and accompanying record paths for a future
   consumer.

The completed handoff establishes which registered data were staged. A future
training integration must pass that dataset to its loader and preserve the
associated record in its Run Record. This implementation neither invokes that
consumer nor claims to prove its behavior.

Data storage uses an already configured DVC remote; production can use GCS.
No bucket creation, region selection, authentication setup, or cloud-resource
discovery belongs here. Same-region GCS/GCE placement remains an external
deployment responsibility.

Register all supplied regular files with their relative names. Do not impose
`images/annotations/`, flatten directories, rename masks, repair pairings, or
infer augmentation history from filenames. The supplied audit data's
`images/masks/` layout must work unchanged. Dataset semantic validation and
training-specific selection are outside this generic registration boundary.
For this version, stage the complete registered Dataset; callers register a
subset as its own Dataset with supplied lineage before staging it separately.

## 3. Minimal implementation structure

Create an independent package under `data_flow_rewrite/`:

| File | Responsibility |
| --- | --- |
| `workflow.sh` | The sole command-line interface: parse shell arguments and invoke Python functions. |
| `workflow.py` | Registration, catalogue packaging, publication, staging, and verification functions; no Python CLI. |
| `pyproject.toml` and `uv.lock` | An isolated environment with pinned DVC dependencies and test tools. |
| `tests/test_workflow.py` | Behavioral tests through the shell interface and real local DVC storage. |
| `.gitignore` | Exclude this package's environment, runtime state, and test artifacts. |
| `README.md` | Operator contracts, recovery procedure, limits, and deferred Git backup. |

Keep this plan alongside those files. Do not modify old scripts, old tests,
root configuration, or excluded integrations. Do not import project helpers
from the previous implementation. Use standard-library filesystem, JSON,
archive, and hashing facilities where appropriate and DVC's own data machinery
for DVC content identities.

Use Python 3.12, DVC with its GCS support at version 3.67.1, and a compatible
explicitly pinned `dvc-data` version. Start with `dvc-data==3.18.2`; verify its
compatibility against DVC 3.67.1's published dependency constraints before
locking. Lock the resolved environment inside this directory. Do not reuse the
root environment or change its dependencies. Declare any directly imported
installed library, including YAML parsing, in the new package configuration.

Use DVC's Python repository API for DVC operations inside Python, rather than
wrapping CLI subprocesses in Python functions. The shell owns CLI parsing.
Keep the DVC repository API and native hashing use confined to this one module;
do not introduce a framework, plugin mechanism, or generic storage wrapper.

## 4. Identity and provenance contracts

### Dataset identity

The caller ID names one immutable registration in a managed catalogue.
Treat it as an opaque string. Use a deterministic SHA-256 of its UTF-8 bytes
for a safe internal directory name; preserve the original ID in record metadata.
This avoids turning caller identifiers into filesystem paths. Check the stored
ID on lookup rather than relying only on its directory name.

The native DVC directory hash identifies the registered filenames and file
contents. It is distinct from the caller's registration identity. Equal contents
may have distinct source histories and distinct IDs.

Apply this registration matrix:

| Existing catalogue state | Without `--force` | With `--force` |
| --- | --- | --- |
| New ID; no matching Dataset hash | Register | Register |
| New ID; matching Dataset hash | Reject and report matching IDs | Register a distinct identity with its supplied provenance |
| Same ID; same hash and provenance | Reject and request `--force` | Reuse the immutable registration; permit publication retry |
| Same ID; changed hash or provenance | Reject | Reject |

Match complete Dataset directory hashes, not individual repeated file hashes.
Compare provenance as parsed JSON values, ignoring object-key ordering and
formatting. Do not add timestamps or transient paths to identity comparisons.
The workflow flag is not permission to overwrite a DVC output, delete data, or
weaken validation.

### Supplied provenance

Use a small version-1 input contract, chosen for this implementation rather
than asserted as an existing project schema:

- `origin`: `acquired`, `derived`, or `inference`.
- `source_refs`: a nonempty list of nonempty strings resolving retained source
  records or stores. References must remain useful after the worker disappears.
- `lineage_ref`: required for `derived`; one retained reference sufficient to
  locate the parent Dataset and applied changes for each relevant data item.
- `model_ref`: required for `inference`; a reference from the caller's existing
  model catalogue, not a newly invented model identifier.

Permit `lineage_ref` and `model_ref` on other origins when applicable. Reject
unknown fields in this initial contract so spelling mistakes cannot silently
discard provenance. Preserve supplied reference strings exactly. Validate
required fields and types locally; do not fetch external catalogues or invent
their contents. The caller is responsible for those references' resolvability
and correctness. A dataset path existing only on a worker is not a durable
source reference.

Store the version, original Dataset ID, and provenance in the `.dvc` record's
top-level `meta` field. Do not duplicate the dataset membership in another
project manifest. The `.dir` index already supplies individual relative paths
and hashes. Confirm `meta` acceptance and round-trip preservation in the pinned
DVC version as part of the first compatibility test.

## 5. Catalogue, records, and portable storage

Use one directory `.dvc` record and native `.dir` index per Dataset ID. The
record's output is a sibling directory named `dataset`. Retain the exact record
bytes once the identity and provenance have been added.

The managed local workspace has separate areas for:

- Per-registration isolated DVC repositories and their dataset copies.
- A metadata catalogue containing one record and native index per ID.
- Metadata archives and their DVC tracking descriptors.
- Temporary work owned by the current operation.

Each registration repository is independent and uses no SCM integration. Do
not initialize DVC in the surrounding project or discover/inherit its stages,
hooks, remotes, ignore files, or dataset ownership. Set cache links to `copy`:
the caller's source, managed cache, and staged dataset must not share mutable
hardlinks.

Package the catalogue metadata into a standard tar archive. It contains only
the per-ID `.dvc` records and their native indexes, outside any dataset. Using
an archive prevents embedded tracking files from being discovered as active
stages while publishing the catalogue. Archive names, ordering, permissions,
and timestamps are normalized so identical metadata produces identical bytes.
Do not include credentials, machine-specific DVC configuration, runtime logs,
caches, or dataset files in this archive.

Track and push this archive through DVC separately from the Dataset contents.
Each successfully published archive is an immutable catalogue snapshot and
contains all registrations known to that catalogue. Retain earlier snapshots;
do not run remote garbage collection or remove historical data in this workflow.

The archive's native `.dvc` descriptor is the bootstrap reference. Its output
path is the fixed local name `catalogue.tar`. Return that descriptor and the
non-secret remote locator to the caller. Credentials remain external and use
the normal DVC authentication mechanism. The caller must retain the descriptor
and remote locator outside ephemeral workers: DVC cannot recover a lost
catalogue pointer from an arbitrary caller ID alone.

Registration operates against the caller's current catalogue snapshot. Exact
hash detection and ID immutability cover that catalogue, not unrelated remotes
or independently forked snapshots. Support one catalogue writer at a time;
take a local workspace lock and fail rather than run simultaneous writers.
Cross-machine coordination and latest-pointer services are not implemented.

## 6. Shell interfaces and operation behavior

The following are interface signatures, not ready-to-run operator commands:

| Operation | Required inputs | Optional inputs | Success result |
| --- | --- | --- | --- |
| `register` | `--dataset`, `--id`, `--provenance`, `--workspace`, `--remote-url`, `--catalogue` | `--force`, `--new-catalogue` | ID, Dataset hash, published catalogue descriptor path |
| `stage` | `--catalogue`, `--id`, `--destination`, `--remote-url` | None | ID, Dataset hash, dataset path, record path, index path |
| `verify` | `--staged` | None | ID, Dataset hash, dataset path, record path, index path |

`--catalogue` names a local bootstrap descriptor. Registration requires it to
exist unless `--new-catalogue` is explicitly supplied. That flag requires the
descriptor not to exist and deliberately starts an empty catalogue. Never
silently start over because a descriptor was lost or a download failed.

The shell rejects unknown flags and missing or duplicate arguments. Emit one
JSON result to stdout only after success; send progress and actionable errors
to stderr. Use exit status 0 for success, 2 for invalid inputs or a policy
rejection, and 1 for operational failures or verification mismatches. Do not
print credentials or authorization-bearing URLs.

### Register

1. Validate inputs and supplied provenance. Reject empty datasets, symlinks,
   special files, and embedded DVC/Git control files that would alter traversal
   or hide files. Do not require particular image or annotation folder names.
2. Lock the workspace. Restore and validate the supplied catalogue snapshot,
   unless an explicit new catalogue is being created.
3. Copy the supplied Dataset into a fresh operation-owned registration
   repository as `dataset`. Hash and register the copy using native DVC.
   Do not edit the source or adopt the old repository's configuration.
4. Apply the identity/duplicate matrix against the complete catalogue. On
   rejection, do not change the published descriptor or existing registrations.
5. Add the validated ID and provenance metadata to the new record. Retain its
   native index. Re-verify the managed copy against that index before publishing.
6. Push the selected Dataset's cached objects and directory index through DVC.
7. Build the extended metadata snapshot, register its archive, and push that
   archive through DVC. Do not report publication from push's exit code alone:
   require a targeted remote-status check with no missing objects for each
   published output. Treat missing-cache warnings or incomplete status as failure.
8. Only after both publications succeed, atomically install the new local
   bootstrap descriptor at `--catalogue` and emit the success result. Preserve
   the previous descriptor as an immutable snapshot in the workspace.

For an existing identical ID with `--force`, preserve the original record bytes
and provenance. Reuse or restore that registration and retry publication; do not
make a second ID or replace metadata.

### Stage

1. Require a nonexistent or empty destination. Never clear or overwrite an
   existing nonempty directory.
2. Work in a sibling temporary directory owned by this operation. Initialize
   an isolated no-SCM DVC repository with the supplied remote.
3. Validate and pull the metadata archive through its bootstrap descriptor.
   Reject descriptors with unexpected outputs, dependencies, working-directory
   changes, or escaping paths before allowing DVC to materialize them.
4. Extract only validated regular archive members. Reject absolute paths,
   traversal, links, duplicate entries, and malformed catalogue records. Resolve
   the selected ID and retain its exact `.dvc` record and native index.
5. In a separate isolated retrieval repository, use that record to pull the
   selected dataset. Do not pull unrelated Dataset contents from the catalogue.
6. Copy the dataset and selected metadata to the final handoff layout, verify
   them, and atomically install the completed handoff at the destination.
7. Emit success only after verification. Remove operation-owned temporary
   files on failure without modifying the destination's prior contents.

The handoff layout is fixed:

```text
destination/
  dataset/
  dataset.dvc
  dataset.dir
```

`dataset.dvc` is the original registered record and resolves `dataset/` by
relative path. `dataset.dir` is an exact copy of the native index whose digest
is referenced by that record. It is outside the dataset to avoid self-inclusion.
The handoff contains no credentials and does not depend on symlinks or a live
retrieval repository. Moving the entire directory preserves verification.

### Verify

1. Validate the selected record and supported metadata version. Read its caller
   ID, provenance, single relative output path, algorithm, and directory digest.
2. Hash the retained index bytes using the recorded algorithm and compare with
   the record's index digest, accounting for DVC's `.dir` suffix.
3. Build a fresh native DVC directory tree from `dataset/` and compare its
   native directory digest with the record. Use a fresh hash state, include all
   regular files, and reject control files or links rather than allowing ignore
   rules to hide extra contents. Do not trust saved mtime-based hash state.
4. Use DVC's pinned hashing/tree implementation; do not recreate its JSON
   serializer or compare MD5 values with SHA-256 values. Native index paths and
   hashes establish individual membership as well as aggregate content identity.
5. Return the handoff paths and identity on success. A mismatch must identify
   the failed boundary and stop; it must not rewrite the expected record.

Successful value comparisons are sufficient evidence for these boundaries.
Do not add tensor auditing, per-read instrumentation, a second manifest format,
or hypothetical failures of ordinary comparisons.

## 7. Failure handling and bounded assumptions

- External catalogue references are preserved and validated structurally. Their
  availability is the caller's responsibility; no external lookup is implied.
- Uploaded but unreferenced objects may remain after an interrupted publication.
  Keep them; automatic remote deletion is outside scope. The prior published
  descriptor remains authoritative until the new one is installed.
- Always distinguish a locally registered version from a successfully published
  version. Never emit a success descriptor for partial publication.
- The registration identifies the copied bytes. Callers must finish producing
  the source before registration; this workflow is not a snapshot service for
  concurrently written source directories.
- Verification describes the staged bytes when it runs. Future consumers must
  use that dataset without modifying it; enforcing their behavior is excluded.
- Native DVC hashes are used for normal content identity and accidental-change
  detection. Do not introduce a second content-addressing system or claim that
  MD5 provides adversarial authenticity or provenance on its own.
- Do not log secrets, serialize authentication state, or load unrelated root
  environment files to discover storage settings.

## 8. Implementation sequence

1. Establish the independent environment and shell/function boundary. Verify
   pinned DVC supports directory registration, `meta`, targeted push/pull, native
   hashing, and remote status through the selected APIs. Check primary DVC
   specifications/source rather than existing project implementations.
2. Implement and test record/provenance validation, immutable identity handling,
   and fresh directory/index verification.
3. Implement registration and targeted dataset publication, followed by the
   deterministic catalogue archive and descriptor commit point.
4. Implement isolated catalogue recovery, selected-dataset staging, portable
   handoff construction, and verification before destination installation.
5. Add the full behavioral test matrix and operator documentation. Record
   actual passing evidence, remaining limits, and deferred Git backup.

Keep functions small and direct. Add no service, database, generalized workflow
engine, legacy adapter, automatic data acquisition, or augmentation executor.

## 9. Validation and acceptance

The highest test seam is the new shell interface against real DVC and an
isolated local filesystem remote. Use the same implementations for publication,
recovery, hashing, and verification as the production workflow. Do not mock
successful comparisons, cache restoration, or the entire storage boundary.

Before any trial:

1. Create a project-root temporary directory containing a new UUID; store the
   UUID in agent memory as the user requires.
2. Add a precise local ignore entry and an operations document describing its
   purpose, creation, commands, and cleanup.
3. Copy the complete `data/augmented/` into it. Use copies for trials and retain
   a source SHA-256 map to check the original remains unchanged.
4. Keep repositories, remotes, test state, logs, and intermediate datasets within
   that temporary directory. Use bounded command timeouts.
5. On completion or failure, verify the original source, remove the trial
   directory and its exact ignore entry, and retain a concise result summary
   under `data_flow_rewrite/`.

Test these externally visible outcomes:

| Scenario | Required outcome |
| --- | --- |
| First registration and publication | Stable caller ID, native hash, retained provenance, recoverable descriptor. |
| Recovery after removing all working data and caches | Restore using only the retained descriptor, remote locator, and remote objects. |
| Stage one ID from a multi-Dataset catalogue | Retrieve its dataset and records without restoring unrelated datasets. |
| Move the completed handoff | Verification still succeeds through relative paths. |
| Repeat identical ID without/with force | Reject without force; preserve exact record and permit retry with force. |
| Different ID with identical Dataset hash | Reject without force; retain separate IDs/provenance with force. |
| Reuse an ID with changed contents or provenance | Reject even with force; retain prior registration. |
| Reorder JSON object keys only | Treat provenance as unchanged. |
| Repeated bytes under different filenames | Preserve all distinct index entries. |
| Changed image or mask; missing, extra, or renamed file | Fail verification. |
| Damaged index or unrelated `.dvc` record | Fail verification without rewriting evidence. |
| Malformed references or missing inference model reference | Reject before publication. |
| Symlink, special file, unsafe archive, or escaping descriptor | Reject without reading/writing outside the operation boundary. |
| Nonempty destination | Reject without changing its contents. |
| Push failure, absent cache object, or incomplete remote status | No successful descriptor update or success result. |
| Retry after partial publication | Recover without replacing an existing identity. |
| Original supplied audit data | Remain byte-for-byte unchanged; preserve existing missing-mask observations. |

The eight motion-blur images reported without same-stem masks are not repaired
or silently removed. Registration tests cover their bytes and names, not whether
the collection is valid input for a particular training loader.

Run formatting, lint, shell syntax, and the focused workflow tests in the new
environment. Do not run existing training tests, cloud calls, Terraform, or
MLflow. Local remote validation proves workflow mechanics, not production GCS
credentials, regional placement, or downstream training readiness.

## 10. Completion and deferred work

The implementation is complete when the new shell workflow registers, publishes,
recovers, stages, and verifies copied audit data; all identity and rejection
cases pass; original data remain unchanged; temporary state is cleaned; and the
new README records the portable handoff and bootstrap-retention contracts.

Record this explicit follow-up: **Implement Git backup of the DVC catalogue
metadata and retained bootstrap descriptors. The user confirmed it will be
used.** The initial implementation performs no Git operations.

Training/MLflow integration, producer integration, cloud provisioning, remote
garbage collection, catalogue concurrency across machines, and migration or
repair of the previous implementation remain outside this rewrite.
