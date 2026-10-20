# Project Instructions

This is the canonical shared guidance for agents working in Feral Vision.
Platform entrypoints link here instead of maintaining copies.

## Correctness and error handling

Write good code. Test it effectively and efficiently instead of catching errors
that won't reasonably occur given the codebase.

An exception to this rule requires identifying a concrete case where the catch
is demonstrably useful and establishing that catching the error is the best
way to handle that case. Keeping execution running is not sufficient by itself.

## File Format

Dated project documents use `YYYY-MM-DD-{activity_name}`. The `activity_name`
is the name of the sprint, if one is active. If the activity name is not known,
ask the user.

Code files and agent instruction files, including files under `docs/agents/`,
do not use this naming convention.

## Code location

[Module layout](../domain/modules.md) is authoritative for the released library,
templates, production implementation, and development tools. The released
`src/sightkit_learn/` package contains reusable behavior; concrete recipes,
cloud resources, and acquisition scripts live in `feral-vision/`.

The library includes the training loop and reusable training orchestration.
Executable control flow is not evidence that code is production-specific.
Before reviewing training code or classifying it for release, read
[Training architecture](training.md).

The generic library must not import production scripts, configuration files,
or other project code outside its library package.

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

### Mandatory Google Cloud skills

Before planning, reviewing, implementing, or executing Google Cloud operations,
read and apply the skills below for the applicable scope. This includes
read-only checks, Terraform, client libraries, REST APIs, and shell scripts;
skills are not optional CLI helpers.

| Scope | Required skill |
| --- | --- |
| All Google Cloud operations: establish the caller, execution environment, target, authentication, and authorization | [google-cloud-recipe-auth](../../.agents/skills/google-cloud-recipe-auth/SKILL.md) |
| Cloud Storage bucket/object operations and configuration, including reads, transfers, access, lifecycle, and retention | `google-cloud-storage:google-cloud-storage-basics` |
| Designing or creating a new Cloud Storage bucket, including through Terraform or a client library | [google-cloud-storage-bucket-architect](../../.agents/skills/google-cloud-storage-bucket-architect/SKILL.md) |

Resolve the Cloud Storage plugin skill by name from the session's available
skills; do not hard-code a machine-specific plugin installation path. Bucket
creation requires both the storage basics and bucket architect skills. Use
storage basics for existing buckets; do not invoke bucket architect outside
its creation scope.

State which skills are being applied. If a required skill cannot be found or
read, report the missing skill and stop the affected work rather than silently
substituting remembered guidance. Follow the skill's relevant references and
apply its requirements to the actual operation, not merely mention its name.

Before any cloud resource attempt, use the applicable repository documentation,
existing configurations, workspace context, and available non-cloud tools to
establish the intended behavior and prerequisites. Do not use live cloud calls
as discovery; proceed decisively only after that local investigation supports
the action.

The one sanctioned live read is the training-image check. Before you say that
the training image is missing, or build it, run
[`feral-vision/scripts/cloud/check_training_image.sh`](../../feral-vision/scripts/cloud/check_training_image.sh).
See [Check for an existing image first](cloudops.md#check-for-an-existing-image-first).

## Agent references

| If your task involves… | Reference | File contents |
| --- | --- | --- |
| project architecture or system integration | [Program flow](program-flow.md) | Data, model-sourcing, and cloud-training flows. Tool ownership: **DVC**. |
| training code, training contracts, or deciding whether training code belongs in the release | [Training architecture](training.md) | Library training behavior versus concrete Hydra/Terraform choices; brownfield review constraints. |
| inference, MLflow model reloading, or prediction input/output contracts | [Inference](inference.md) | Native MLflow loading, Hydra configuration, prepared inputs, and preserved model outputs. |
| tensor dtypes, mixed precision, quantization, or device precision support | [Data types and execution precision](../guide/precision.rst) | Hardware/runtime choices, target dtype preservation, and current AMP limitations. |
| project code or authored documentation | [Coding standards](coding-standards.md) | Documentation and code-quality requirements. |
| user-facing chat, summaries, or an operator command | [User interactions](user-interactions.md) | User-facing collaboration preferences, CLI ownership, and copy-pasteable command requirements. Tool ownership: **Scripts and source code**. |
| Python tests, fixtures, or model examples | [Test writing and review](testing.md) | Pytest best practices, mocking scope, and test-data rules. |
| data ingestion, dataset layout, or publication | [Data and ingestion](data.md) | Dataset layout, publication, lineage, and acquisition. Tool ownership: **DVC**. |
| Hydra or model configuration | [Configuration](configuration.md) | Recipe and reproducibility requirements. Tool ownership: **Hydra**. |
| locating a Hydra configuration concern | [Hydra configuration index](hydra.md) | Configuration README index by concern. Tool ownership: **Hydra**. |
| Terraform modules, state, plans, or Cloud Resource lifecycle | [Terraform](terraform.md) | Terraform ownership, file map, state, and plan safety. Tool ownership: **Terraform**. |
| cloud identity, image builds, VMs, or cloud training | [Cloud Operations](cloudops.md) | Cloud-service credentials and operational entrypoints. Tool ownership: **Scripts and source code**. |
| **a claim that the training image is or is not built, or a decision to build it** | [Check for an existing image first](cloudops.md#check-for-an-existing-image-first) | **Run `feral-vision/scripts/cloud/check_training_image.sh` first.** Earlier agents built the image, forgot, and said it did not exist. |
| Git, GitHub Issues, pull requests, or publishing | [GitHub workflow](github.md) | Session checks, authentication, issue tracking, and branch/PR hygiene. |
| domain terminology or an architectural decision | [Domain Docs](domain.md) | Glossary and ADR discovery. |
| an agent reached for the wrong tool or source despite these routing instructions | [Pointer failures](pointer_failures.md) | Log of wrong-tool and wrong-source selections, with the agent's stated reason. |
| downloading or working directly with models that might come from Hugging Face | [`model-inspector` MCP server](../../.mcp.json) | The MCP 2 stdio server is not available until a client launches `mcp/server/main.py` (`uv run --frozen python mcp/server/main.py`). Connect to it before you touch the model. |
| a Wayfinder map or child ticket | [Wayfinding](wayfinding.md) | Map, child-ticket, dependency, and frontier conventions. |
| GitHub issue workflow labels | [Triage Labels](triage-labels.md) | Canonical labels and their meanings. |
