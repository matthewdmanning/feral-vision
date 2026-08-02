# Project Instructions

This is the canonical shared guidance for agents working in Feral Vision.
Platform entrypoints link here instead of maintaining copies.

All agents must read the [glossary](../domain/glossary.md) for project-specific vocabulary and [triage labels](triage-labels.md) for workflow definitions.

Read only the sections and linked documents required for the task you were
instructed to perform. Follow an explicitly required reference before acting;
otherwise, do not load unrelated guidance merely because it is listed here.

> **Temporary cloud startup note.** Before resuming Google Cloud delivery work,
> install or load the official Google Cloud capability set: the
> `google-cloud-storage` Codex plugin plus the `gcloud` and
> `google-cloud-recipe-auth` skills. Remove this note once the required
> capabilities are available in the standard agent environment.

## Tool ownership

- **DVC** owns raw, processed, and augmented Datasets and Dataset Artifacts. It
  does not own training or evaluation runs, checkpoints, or metrics.
- **Hydra** owns tunable configuration in `conf/`; complete named Run Recipes
  own executable selection.
- **MLflow** owns run metrics, artifacts, checkpoints, metadata, and links from
  model versions to Dataset Artifacts. Raw data directories must not be logged
  to MLflow.
- **MLflow Model Registry** owns Registered Models; its offline journal is only
  a retry buffer.
- **Scripts and source code** own workflow control.

## Agent references

- [Program flow](program-flow.md) - architecture and integration
- [Implementation workflow](implementation.md) — code and authored-documentation
  changes
- [Test writing and review](testing.md) — required skill and availability gate
- [Data and ingestion](data.md) — dataset layout and publication
- [Configuration](configuration.md) — Hydra recipes and model reproducibility
- [Hydra configuration index](hydra.md) — configuration README files by concern
- [Tracking and data integration](tracking.md) — tracking-specific operational
  guidance
- [GitHub workflow](github.md) — repository session checks, GitHub
  authentication, issue tracking, and branch, commit, and pull-request hygiene
