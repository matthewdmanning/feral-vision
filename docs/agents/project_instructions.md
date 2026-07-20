# Project Instructions

This is the canonical shared guidance for agents working in Feral Vision.
Platform entrypoints link here instead of maintaining copies.

## Session prerequisites

At the beginning of a session, check that `gh` is installed, `origin` is set,
MCP servers respond, and any scripts needed for the task are available. Report
each missing or broken prerequisite with a concise fix, then stop before work
that depends on it.

## Program flow and repository orientation

Read [ARCHITECTURE.md](../../ARCHITECTURE.md) before architecture or integration
work. It is the single source of truth for the data-to-model program flow and
tooling ownership; link to it instead of restating that flow elsewhere.

The reusable package is under `src/feral_vision/`; project-specific workflow,
deployment, and operational code belongs in `scripts/`. Model configuration and
source adapters are owned by `models/register_model.py` and `models/sources/`.
The canonical training entrypoint is `training/trainer.py`.

## Commands

```bash
# Tests (use -m on Windows)
uv run python -m pytest
uv run python -m pytest tests/test_augmentations.py -v

# DVC data pipeline
dvc repro
dvc pull

# Augmentation
uv run python scripts/augment.py --src tests/fixtures --dst data/augmented/coco_train17 --ops motion_blur original

# GCP training (requires GCP_PROJECT and GCS_BUCKET)
GCP_PROJECT=my-proj GCS_BUCKET=my-bucket bash scripts/gcp_train.sh
```

## Dataset contract

Every dataset root has `images/` and `annotations/` directories. Annotation
files match image stems: masks use `.png` or `.jpg`, YOLO boxes use `.txt`, and
classification labels use `.json`; `names.yaml` records class indices. The data
source dispatch in `data/fetch.py` must resolve every source to this layout.

## Configuration rules

Do not modify an existing Hydra `default.yaml` in place. Create a semantic named
replacement; the planned configuration cutover retires legacy defaults only
after the replacement recipes are validated. A required architecture `location`
must always be non-null so a model remains reproducible.

All tunables belong in `conf/`. Consult the co-located configuration README for
the concern's purpose and use a complete named Run Recipe for reproducible work.

## Environment and documentation

GCP training requires `GCP_PROJECT` and `GCS_BUCKET`. Find installed-version
documentation first; use Context7 only when local documentation is unavailable.
For product scope and delivery constraints, see
[Product Scope](../planning/product-scope.md). The domain glossary is
[CONTEXT.md](../../CONTEXT.md).

## GitHub access

Follow the canonical [issue-tracker guidance](issue-tracker.md) for GitHub
Issues and pull-request work. Prefer the connected GitHub app when it supports
the operation. For CLI work, authenticate `gh` from the local `.env.local`
token without printing or committing secret values, then verify with
`gh auth status`.

## Git workspace hygiene

Never push directly to `main`; publish changes through a pull request. Create
commits with `uv run cz commit`; the Dev workflow validates Conventional Commit
messages on non-`main` branches.

Do not leave stale Git worktrees or branches behind. Before finishing work,
remove worktrees and local branches created for the task once they are no longer
needed. Check their status first, and never remove an active, dirty, or
user-owned worktree or branch without explicit approval.

## Scope and tool boundaries

Scope strictly to the task at hand. See
[ARCHITECTURE.md](../../ARCHITECTURE.md#7-tooling-boundaries) for DVC, Hydra,
MLflow, source-code, and model-registry ownership. Never log raw data
directories to MLflow; use DVC references or locks for data lineage instead.

When writing a pull-request description, use
[the repository template](../../.github/PULL_REQUEST_TEMPLATE.md) and include
only sections relevant to the change.

## Agent references

- [Issue tracker](issue-tracker.md)
- [Triage labels](triage-labels.md)
- [Domain documentation](domain.md)
