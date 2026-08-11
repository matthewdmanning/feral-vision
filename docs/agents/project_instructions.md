# Project Instructions

This is the canonical shared guidance for agents working in Feral Vision.
Platform entrypoints link here instead of maintaining copies.

## File Format

Dated project documents use `YYYY-MM-DD-{activity_name}`. The `activity_name`
is the name of the sprint, if one is active. If the activity name is not known,
ask the user.

Code files and agent instruction files, including files under `docs/agents/`,
do not use this naming convention.

## Code location

Place code that is agnostic to a particular model, data source, bucket, or
server in `src/feral_vision/`. Place code specific to a configuration, model,
augmentation composition, data source, bucket, or server in an appropriate
subfolder of `scripts/`.

Code under `src/` must **never** import from a project file or subfolder outside
`src/`.

## Routing

All agents must read the [glossary](../domain/glossary.md) for project-specific vocabulary.

Read only the sections and linked documents required for the task you were
instructed to perform. Follow an explicitly required reference before acting;
otherwise, do not load unrelated guidance merely because it is listed here.

## Dated documents

When a folder contains documents named `YYYY-MM-DD-{activity_name}`, read only
the document with the most recent date. Naming determines recency; all earlier
dated documents in that folder are stale unless the user explicitly asks for
one.

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

## Cloud change discipline

Before any cloud resource attempt, use the applicable repository documentation,
existing configurations, workspace context, and available non-cloud tools to
establish the intended contract and prerequisites. Do not use live cloud calls
as discovery; proceed decisively only after that local investigation supports
the action.

## Agent references

| If your task involves… | Reference | File contents |
| --- | --- | --- |
| project architecture or system integration | [Program flow](program-flow.md) | Data, model-sourcing, and cloud-training flows. Tool ownership: **DVC**. |
| project code or authored documentation | [Coding standards](coding-standards.md) | Documentation and code-quality requirements. |
| user-facing chat, summaries, or an operator command | [User interactions](user-interactions.md) | User-facing collaboration preferences, CLI ownership, and copy-pasteable command requirements. Tool ownership: **Scripts and source code**. |
| Python tests, fixtures, or model examples | [Test writing and review](testing.md) | Required testing skill and test-data rules. |
| data ingestion, dataset contracts, or publication | [Data and ingestion](data.md) | Dataset layout, publication, lineage, and acquisition contracts. Tool ownership: **DVC**. |
| Hydra or model configuration | [Configuration](configuration.md) | Recipe and reproducibility requirements. Tool ownership: **Hydra**. |
| locating a Hydra configuration concern | [Hydra configuration index](hydra.md) | Configuration README index by concern. Tool ownership: **Hydra**. |
| Terraform modules, state, plans, or Cloud Resource lifecycle | [Terraform](terraform.md) | Terraform ownership, file map, state, and plan safety. Tool ownership: **Terraform**. |
| cloud identity, image builds, VMs, or cloud training | [Cloud Operations](cloudops.md) | Cloud-service credentials and operational entrypoints. Tool ownership: **Scripts and source code**. |
| Git, GitHub Issues, pull requests, or publishing | [GitHub workflow](github.md) | Session checks, authentication, issue tracking, and branch/PR hygiene. |
| domain terminology or an architectural decision | [Domain Docs](domain.md) | Glossary and ADR discovery. |
| a Wayfinder map or child ticket | [Wayfinding](wayfinding.md) | Map, child-ticket, dependency, and frontier conventions. |
| GitHub issue workflow labels | [Triage Labels](triage-labels.md) | Canonical labels and their meanings. |
