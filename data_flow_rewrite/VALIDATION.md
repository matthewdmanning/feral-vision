# Rewrite validation

Run: 2026-10-16 17:37:09 (UTC). Trial UUID: `75c5cea0-ac3f-4e64-948e-448daacbe5cd`. Exit status: 0.

Environment: Python 3.12, DVC 3.67.1, dvc-data 3.18.2; isolated local filesystem remote.

```text
PASS 01 first native registration, metadata archive publication, and JSON result
PASS 02 native index preserves repeated bytes under distinct filenames
PASS 03 identical-ID retry needs force and preserves exact deterministic snapshot
PASS 04 same complete Dataset hash requires force for a distinct identity
PASS 05 provenance object ordering does not alter identity
PASS 06 changed provenance cannot replace an ID even with force
PASS 07 derived lineage is retained in the original DVC record
PASS 08 inference model catalogue reference is accepted and retained
PASS 09 changed bytes cannot replace an ID; a different dataset can register separately
PASS 10 cache-free recovery selects one dataset from a multi-Dataset catalogue
PASS 11 selected staging ignores missing unrelated objects; an unrelated record fails verification
PASS 12 portable handoff verifies after being moved
PASS 13 changed image and mask are rejected
PASS 14 missing, extra, and renamed files are rejected
PASS 15 damaged native index and escaping records fail without rewriting evidence
PASS 16 symlinks, special files, and ignore controls cannot hide dataset contents
PASS 17 nonempty staging destination is preserved
PASS 18 missing model/lineage, malformed references, unknown fields, and duplicate JSON keys are rejected
PASS 19 shell rejects unknown operations, flags, duplicate and missing values
PASS 20 escaping bootstrap descriptor is rejected before materialization
PASS 21 simultaneous local writer fails without publication
PASS 22 push failure produces no success JSON or bootstrap descriptor
PASS 23 retry after partially completed publication recovers
PASS 24 missing remote cache object stops staging and preserves empty destination
PASS 25 original synthetic source unchanged; final handoff still verifies
PASS 26 metadata upload failure preserves the prior bootstrap and can be retried
PASS 27 traversal archive published through real DVC is rejected before extraction
PASS 28 symlink, duplicate, absolute, and malformed metadata archives are rejected
PASS 29 relative input paths and opaque flag-like IDs round-trip
PASS 30 empty and linked source trees, lost bootstrap, and unknown IDs fail safely
PASS 31 earlier immutable bootstrap remains recoverable after catalogue extension
PASS 32 verified staging atomically replaces an empty destination
PASS 33 fresh DVC hashing detects changed bytes despite identical size and mtime
PASS 34 local remote overlapping the source is rejected without modifying the source
PASS 35 validated retained index prevents unsafe remote index paths from controlling retrieval
Completed 35 behavioral checks
```

Supplied-data trial: Not run: data/augmented/ is absent from this checkout.

No Python tests were written: required `write-python-test` skill is unavailable. The executable shell suite covers the public CLI with real DVC.

GCS authentication, regional deployment, producer/training/MLflow integration, and cross-machine concurrency were not tested.

Trial tree and its exact local ignore entry are removed on exit. No supplied source files are modified.

Final static checks passed: `ruff check`, `ruff format --check`, and `bash -n`
on the new module and shell entrypoints. `git diff --check` passed. Comparison
against integrated `origin/main` confirms no authored changes to `src/`,
`scripts/`, `conf/`, root `pyproject.toml`, root `uv.lock`, or root `.gitignore`.
The independent `.venv` remains locally installed and ignored.

Branch preparation: `feat/dvc-data-flow-rewrite` was at its fetched remote tip.
It diverged from current `main`, so a fast-forward was impossible; a local merge
integrated `origin/main` without conflicts. Rewrite implementation files remain
uncommitted for review. No push or PR was performed.
