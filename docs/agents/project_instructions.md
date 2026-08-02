# Project Instructions

This is the canonical shared guidance for agents working in Feral Vision.
Platform entrypoints link here instead of maintaining copies.

All agents must read the [glossary](glossary.md) for project-specific vocabulary and [triage labels](triage-labels.md) for workflow definitions.

Read only the sections and linked documents required for the task you were
instructed to perform. Follow an explicitly required reference before acting;
otherwise, do not load unrelated guidance merely because it is listed here.

> **Temporary cloud startup note.** Before resuming Google Cloud delivery work,
> install or load the official Google Cloud capability set: the
> `google-cloud-storage` Codex plugin plus the `gcloud` and
> `google-cloud-recipe-auth` skills. Remove this note once the required
> capabilities are available in the standard agent environment.

## Agent references

- [Program flow](program-flow.md) - architecture and integration
- [Development workflow](development.md) — repository layout, commands, and
  documentation lookup
- [Test writing and review](testing.md) — required skill and availability gate
- [Data and model tests](data.md) — dataset layout and image-shaped test inputs
- [Configuration](configuration.md) — Hydra recipes and model reproducibility
- [MLOps boundaries](mlops.md) — DVC, Hydra, MLflow, and model-registry scope
- [GitHub workflow](github.md) — repository session checks, GitHub
  authentication, issue tracking, and branch, commit, and pull-request hygiene
