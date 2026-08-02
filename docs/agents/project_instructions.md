# Project Instructions

This is the canonical shared guidance for agents working in Feral Vision.
Platform entrypoints link here instead of maintaining copies.

Read only the sections and linked documents required for the task you were
instructed to perform. Follow an explicitly required reference before acting;
otherwise, do not load unrelated guidance merely because it is listed here.

> **Temporary cloud startup note.** Before resuming Google Cloud delivery work,
> install or load the official Google Cloud capability set: the
> `google-cloud-storage` Codex plugin plus the `gcloud` and
> `google-cloud-recipe-auth` skills. Remove this note once the required
> capabilities are available in the standard agent environment.

## Documentation integrity

Functions longer than three lines and class definitions must have docstrings. All docstrings must be written using numpy style.

The main agent must update the canonical project documentation in the same
change whenever code changes a substantive project contract. This includes
program flow, integrations or deployment paths, runtime/configuration behavior,
data or MLflow ownership, public interfaces, and operator workflows. A purely
internal refactor that preserves those contracts does not require documentation
changes. Do not defer this check to a later session or reviewer.

When a change affects a user-visible workflow, update the relevant document in
`docs/guide/` in the same change. If no guide changes are needed, record that
the guide-impact check was completed in the handoff.

Do not commit `docs/_build/` or run Sphinx as part of local validation:
GitHub Actions rebuilds documentation on documentation changes and deploys the
generated Pages artifact from `main`.

## CLI boundary

Never integrate a CLI into a function or Python script. Only shell scripts may
provide command-line interfaces.

When an operator must make a change, provide the exact complete CLI command in
a standalone `bash` code block. Commands must be directly copy/paste compatible
and include every required flag and value.

## Code quality

Before adding project code for a capability, check whether a library already in
use provides it. Use that library directly unless a project-specific boundary is
genuinely required.

## Agent references

- [Development workflow](development.md) — repository layout, commands, and
  documentation lookup
- [Test writing and review](testing.md) — required skill and availability gate
- [Data and model tests](data.md) — dataset layout and image-shaped test inputs
- [Configuration](configuration.md) — Hydra recipes and model reproducibility
- [MLOps boundaries](mlops.md) — DVC, Hydra, MLflow, and model-registry scope
- [Git and GitHub workflow](git.md) — session checks, `gh` authentication, and
  branch, commit, and pull-request hygiene
- [Issue tracker](issue-tracker.md)
- [Triage labels](triage-labels.md)
- [Domain documentation](domain.md)
