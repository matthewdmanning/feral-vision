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
