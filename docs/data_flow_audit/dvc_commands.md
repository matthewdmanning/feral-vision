# DVC command investigation

Investigation performed on 2026-10-15. The authoritative user instructions and
lifecycle are recorded separately in [instructions.md](instructions.md).
This is an evidence record, not a prescribed project workflow.

## Scope and sources

Investigated `dvc add` and `dvc push`, starting with their inputs and outputs,
then their options. Consulted installed command help, selected installed source
code, and the official command references:

- [dvc add](https://doc.dvc.org/command-reference/add)
- [dvc push](https://doc.dvc.org/command-reference/push)
- [.dvc metadata specification](https://doc.dvc.org/user-guide/project-structure/dvc-files)

Cookbook workflows were not adopted. Existing project documentation was not
treated as authoritative evidence of DVC command behavior.

## Default inputs and outputs

| Command | Inputs | Persistent outputs |
| --- | --- | --- |
| `dvc add` | Selected file/directory paths and contents; applicable DVC configuration and ignore rules. | Creates or updates `.dvc` tracking metadata; caches contents locally; updates Git ignore rules where needed. |
| `dvc push` | Selected tracking records, corresponding cached objects, remote configuration and credentials. | Uploads missing cache objects to the selected remote. Does not upload `.dvc` files or Git commits. |

For a directory, the `.dvc` record points to a `.dir` JSON index in the cache.
That index contains relative filenames and their content hashes. Tracking a
directory does not create a separate `.dvc` file for every contained file.

Console progress, summaries, warnings, and exit status are separate outputs
from metadata and stored objects. Neither command automatically identifies the
original source, applied transformations, parent lineage, or inference model.

The catalogue metadata is distinct from file contents: default `add` and `push`
also manage actual payload storage. This describes tool mechanics without
expanding the user's intended catalogue responsibility for DVC.

## Trial setup and cleanup

- Version: DVC 3.67.1; Linux under WSL; project filesystem reported as 9p.
- UUID: `428536a1-c4df-42c6-b676-a08b1e91a9fb`, stored in agent memory.
- Trial directory: project-root
  `.dvc-options-trial-428536a1-c4df-42c6-b676-a08b1e91a9fb/`.
- The directory was covered by a specific local Git exclude entry and contained
  `OPERATIONS.md`, command logs, copied inputs, isolated Git/DVC repositories,
  local remotes, source hashes, and verification results.
- All trial data came from a complete copy of `data/augmented/`. The existing
  `coco_train17/images/` and `coco_train17/masks/` layout was preserved.
- Filesystem remotes were outside tracked data roots. Trial repositories used
  `cache.type=copy`; no pipelines, hooks, or cloud operations were introduced.
- Each trial DVC command had a 40-second timeout. None timed out.
- The complete trial directory and its exact local ignore entry were deleted
  after verification. Raw trial logs and generated DVC records are consequently
  no longer available; this document records their observed results.
- Original source files were verified unchanged through their SHA-256 map.
  Project DVC configuration, data registrations, and unrelated worktree changes
  were not modified by the trials.

## Supplied data observations

The copy contained 136 files: 72 images and 64 masks, with 96 distinct payload
content hashes. Eight `motion_blur` images had no same-stem mask. No alternative
pairing was inferred and no data was repaired or removed.

The directory index retained all 136 relative filenames, including augmentation
suffixes, even when contents were shared. For example, these two mask filenames
had the same content hash, `ec7f9b5852e0e9433ea003448fe2fe47`:

```text
coco_train17/masks/Bengal_48_brightness.png
coco_train17/masks/Bengal_48_gamma_bright.png
```

DVC preserved these distinct names; it did not interpret the augmentation names
or establish their source relationships.

## Executed trials

Command forms below describe completed isolated trials, not operator commands
for this checkout. `data` was a trial copy, `external-source` denotes the
separate copied source, and `trial` was a local filesystem remote.

| Trial | Observed result |
| --- | --- |
| Default `add data`, then targeted `push data.dvc -r trial -j 2` | One `.dvc` record; 97 completed local cache and remote objects: 96 payload objects plus one directory index. |
| Repeat default `push`, then repeat `add` | Push reported up to date. The repeated add preserved the exact `.dvc` metadata. |
| `add --no-commit data` | One aggregate `.dvc` record; zero cached objects, including no persistent `.dir` index in the cache. |
| `push` after that directory `--no-commit` trial | Warned about missing cache, printed `Everything is up to date.`, returned exit status 0, and uploaded nothing. |
| `add --no-commit` targeting one actual image and its same-stem mask | Two individual `.dvc` records containing filenames and hashes; zero cached objects. |
| `add external-source --out data`, repeated unchanged | Same dataset bytes and aggregate metadata as default add; 97 completed cache objects. Repetition succeeded without `--force`. Two calls also left 272 `.tmp` files in the cache. |
| `add external-source --out data --to-remote -r trial --remote-jobs 2` | Same aggregate metadata; 97 completed remote objects, no workspace `data` directory, and no local cache objects. Also left 136 `.tmp` files in the filesystem remote. |
| `add --no-relink data` | Same dataset bytes, aggregate metadata, and 97 completed cache objects as default add. This option does not disable caching. |
| `add --glob 'data/coco_train17/*'`, then `push --glob 'data/coco_train17/*.dvc'` | Separate image-directory and mask-directory records; 98 cache/remote objects: 96 payload objects plus two directory indexes. |
| `push` selecting one image and its mask inside the directory-tracked Dataset | Transferred three completed objects: the two selected payload objects plus the directory index. This did not publish all other dataset payloads. |

The aggregate directory record observed in the default trial was:

```yaml
outs:
- md5: a79c48b30c18be85051f07455e429868.dir
  size: 4484200
  nfiles: 136
  hash: md5
  path: data
```

One individual image record from the per-file `--no-commit` trial was:

```yaml
outs:
- md5: 9a49f61dd54813cd6c7428c21325bf50
  size: 83100
  isexec: true
  hash: md5
  path: Bengal_48_original.jpg
```

`isexec` is the observed filesystem metadata, not a project data requirement.

## JSON format comparison with the project manifest

Checked against official DVC documentation on 2026-10-15:

| Record | Serialization and structure | Match to `dataset-artifact.json` |
| --- | --- | --- |
| DVC directory cache index, `<hash>.dir` | JSON array of entries containing `relpath` and content hash, commonly `md5`. | Same serialization format, different schema. |
| `.dvc` tracking file | YAML with an `outs` list, tracked path and hash. | Not the project's JSON manifest schema. |
| Project `dataset-artifact.json` | JSON object containing supplied metadata and `files[relative_path] = {sha256, generation}`. | Generated by the project publisher, not by the inspected DVC commands. |

Sources: [DVC directory cache structure](https://doc.dvc.org/user-guide/project-structure/internal-files#directories),
[DVC metadata format](https://doc.dvc.org/user-guide/project-structure/dvc-files),
and [project publisher](../../src/feral_vision/data/dataset_artifact.py).

Thus DVC does produce JSON associated with dataset contents, notably the `.dir`
index. The current project manifest is not that index. Shared JSON serialization
does not establish DVC provenance, schema compatibility, or an association with
the actual training inputs. No replacement format has been selected or trialled
by this comparison.

## Other options inspected, not exercised

| Options | Documented/help behavior |
| --- | --- |
| `add --force` | Permits overwriting an existing destination. Collision behavior was not exercised; the unchanged tracked destination trial did not require it. |
| `push --all-branches`, `--all-tags`, `--all-commits` | Expands the versions considered across Git history. |
| `push --with-deps` | Includes pipeline dependencies of selected targets. |
| `push --recursive` | Searches target directories for nested tracking metadata. |
| `push --run-cache`, `--no-run-cache` | Controls uploading stage-run history. |
| `--quiet`, `--verbose`, `--help` | Controls reporting or displays command help. Help was read; quiet/verbose behavior was not trialled. |

## Verification and corrections during investigation

Verification checked the original source SHA-256 map and all materialized trial
copies; expected metadata/object counts; exact aggregate metadata equality
across default, `--out`, `--to-remote`, and `--no-relink`; and remote payload
content hashes.

Two initial expectations were disproven by execution: missing cache did not
make `push` return nonzero, and repeating `--out` against the unchanged tracked
destination did not fail. Those assumptions were corrected rather than treated
as tool guarantees.

An initial total-file-count assertion exposed the `.tmp` leftovers. Direct
inspection separated temporary files from completed content-addressed objects;
the revised verification passed. The cause and cloud-backend applicability of
those leftovers have not been established.

## Implications for the user-defined lifecycle

- Individual `--no-commit` records retained filenames and hashes without caching
  payloads. A directory `--no-commit` record alone did not persist its individual
  filename/hash index in the cache. These are different catalogue outcomes.
- Successful `push` exit status alone did not prove data publication.
- Filenames can distinguish catalogue entries with identical content hashes;
  preserving a name does not by itself validate the source or lineage it names.
- No tested option automatically supplied source, parent, or inference-model
  identity. Their representation remains to be established against the user's
  requirements.
- These trials did not select a final record format or validate moving required
  DVC files with staged data, MLflow recording the training data used, or
  integration with the existing model catalogue.

No end-to-end lifecycle or cloud behavior has been validated by these trials.

## Training-data association spec — 2026-10-16

This section records the subsequent diagnosis and proposed verification scope.
It does not select a final record format or claim implementation or runtime
validation. The user instructed the analysis to examine input requirements and
available information, including hashes, and to assume scripts compare values
correctly. The authoritative requirements remain in [instructions.md](instructions.md).

### Problem Statement

The MLflow Run Record must preserve a DVC output associated with the Dataset
used for training. The current path preserves a custom manifest and checks its
hash, but does not establish the connection between the registered DVC version,
the manifest, and the staged training data. Identifying the metadata document
alone does not establish which data its contents describe.

### Solution

Establish a continuous association from the registered DVC record, through the
matching staged Dataset, to the loader and the record logged in MLflow. Use
identifiers and successful comparisons at the relevant boundaries. Once the
verified data root is passed to the loader, ordinary script execution establishes
that connection; repeated observation of every individual training read is not
required by this diagnosis.

### User Stories

1. As a training operator, I want the logged DVC output to identify the selected training Dataset, so that the Run Record describes its actual input.
2. As a data maintainer, I want a unique Dataset registration identifier, so that I can resolve the intended catalogue entry.
3. As a data maintainer, I want content hashes to identify registered contents, so that I can compare a staged copy with those contents.
4. As a training operator, I want filenames and membership included in the association, so that matching a few files does not accidentally identify a different Dataset.
5. As a training operator, I want images and their annotations covered together, so that the recorded Dataset describes the training input pairs.
6. As a cloud operator, I want the required DVC records copied with data to ephemeral GCE, so that training can retain the selected registration evidence.
7. As a training operator, I want the loader to receive the verified staged root, so that verification and training refer to the same data.
8. As an experiment reviewer, I want MLflow to retain the associated DVC output, so that the training Dataset can be identified after GCE is deleted.
9. As a data maintainer, I want identifiers to resolve retained source and parent references, so that copying data does not lose Data Lineage.
10. As a data maintainer, I want inference-derived data to resolve the producing model through the existing model catalogue, so that model provenance remains locatable.
11. As a data maintainer, I want distinct registrations to remain distinguishable when their bytes match, so that content deduplication does not erase source history.
12. As a training operator, I want a mismatching input rejected before training, so that unrelated metadata cannot be recorded as its Dataset evidence.

### Implementation Decisions

- The diagnosed gap is an omitted association/comparison, not an incompatibility
  between DVC outputs and MLflow artifact logging.
- The current publisher records relative filenames, SHA-256 values, and GCS
  object generations. Staging checks existence and manifest syntax, then hashes
  the manifest. The container entrypoint compares that manifest hash, and the
  trainer logs the manifest. These operations do not compare its file entries
  against the staged payload or connect it to the separate DVC registration.
- A file content hash identifies bytes for this workflow. A DVC directory hash
  identifies its directory index, whose entries identify relative filenames and
  file hashes. Verifying that representation requires its referenced contents,
  not merely hashing an arbitrary directory listing.
- A unique catalogue identifier or registered filename can distinguish Dataset
  registrations and resolve retained provenance. Equal content hashes alone do
  not distinguish different source histories.
- A GCS bucket, object name, and generation identify a stored object version.
  A manifest hash identifies the exact metadata document. Neither alone checks
  that local training files match the registered contents.
- Compare hashes using the same algorithm and representation. DVC MD5 values
  and the custom manifest's SHA-256 values are not directly comparable.
- A sufficient direct approach is to retain the selected DVC record and any
  required directory index, verify the staged input against its names and
  hashes, pass the verified root to the loader, and log that record to MLflow.
- If the custom manifest remains an intermediary, publication must establish
  its connection to the DVC version, and staging must establish the connection
  between its entries and the training payload. This is an alternative, not a
  decision to retain that manifest or add a second catalogue.
- Verification must account for the loader's input selection. If it consumes
  a subset of a registered Dataset, preserve that selection's association;
  this does not prescribe a new DVC record granularity.
- Relative paths or symlinks can locate staged data. Retained catalogue
  references must still locate root sources and lineage after GCE disappears.
- Identifier format, record layout, provenance schema, and the choice between
  direct verification and a manifest intermediary remain unresolved.

### Testing Decisions

The following seam is proposed, not user-confirmed or implemented: exercise the
staging-to-training handoff through the existing container training entrypoint,
using the real verification and loader construction and a bounded training
operation. Inspect the resulting MLflow evidence. Keep the test at this shared
boundary where practical, rather than testing comparison syntax in isolation.

- A matching Dataset and DVC record should reach training and produce the
  associated logged record.
- A changed image or annotation, or a mismatched DVC record, should be rejected
  before training. Exercise missing and extra loader-visible files as membership
  cases, accounting for any explicitly selected subset.
- Identical bytes under distinct registered names should retain their catalogue
  identities and provenance references.
- Existing publication tests cover manifest filenames, hashes, and object
  generations; the trainer tracking test covers preserving manifest bytes in
  MLflow. These are useful prior art but do not currently prove the full DVC
  association. Deployment tests also inspect entrypoint wiring.
- Test external outcomes: accepted or rejected training input and the record
  retained by MLflow. Do not simulate comparisons mysteriously failing or
  require a second audit of each successful loader read.
- Any trial must follow the existing project-root temporary-folder, copied-data,
  unique-identifier, operations-document, ignore, and cleanup rules.

### Out of Scope

DVC orchestration of training; a mandatory MetaDataset integration; mandatory
per-image DVC files; a mandatory lockfile; a new provenance catalogue; cloud
resource provisioning; and verification of every transformed tensor or read.
This spec does not authorize implementation changes or select unresolved
formats.

### Further Notes

The diagnosis follows the inspected publisher, staging template, container
entrypoint, loader construction, and MLflow logging path. An independently
supplied dataloader accepted by the trainer API does not invalidate the concrete
entrypoint's use of its configured root.

The DVC [tracking-file specification](https://doc.dvc.org/user-guide/project-structure/dvc-files)
and [directory-cache specification](https://doc.dvc.org/user-guide/project-structure/internal-files#directories)
describe the path/hash and directory-index representations used in this analysis.
Existing source evidence is recorded in the
[MLflow findings](mlflow_dvc_findings.md#follow-up-association-in-the-inspected-project-code).
No new trials, cloud operations, or end-to-end training validation were performed.
