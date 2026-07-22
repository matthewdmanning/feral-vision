# Development workflow

Use this guide for repository orientation, local commands, and documentation
lookup.

Read [the program flow](../architecture/program-flow.md) before architecture or
integration work. It is the single source of truth for the data-to-model program
flow and tooling ownership; link to it instead of restating that flow elsewhere.

The reusable package is under `src/feral_vision/`; project-specific workflow,
deployment, and operational code belongs in `scripts/`. Model configuration and
source adapters are owned by `models/register_model.py` and `models/sources/`.
The canonical training entrypoint is `training/trainer.py`.

## Commands

```bash
# Mirrors the Dev and Training smoke GitHub Actions jobs.
bash scripts/validate_ci.sh

# Tests (use -m on Windows)
uv run python -m pytest

# DVC data pipeline
dvc repro
dvc pull
```

For the cloud-training contract and first-run readiness status, see
[Product Scope](../planning/product-scope.md). The operational procedure is
[Docker/GCE training](../../docker/USER_STEPS.md). The domain glossary is
[Glossary](../domain/glossary.md). Find installed-version documentation first;
use Context7 only when local documentation is unavailable.
