# Project Instructions

At beginning of session, check that gh CLI is installed, git remote origin is set, and MCP servers respond, and any scripts I rely on. For each broken or missing tool, give me an alert and a concise fix. Report any missing prerequisites and stop if something is broken.

## Program Flow — Read Before Architecture/Integration Work

`ARCHITECTURE.md` (repo root) is the single source of truth for program flow — data acquisition through a trained model checkpoint (data source, augmentation, dataset loading, model acquisition, training, tooling boundaries). If you are doing architecture or integration work, read it before making design decisions or describing this project's flow. Do not restate or re-derive program flow elsewhere; link back to `ARCHITECTURE.md` instead, and update it in the same change if it goes stale.

## Commands

```bash
# Tests (NOTE: uv run pytest fails on Windows — use -m flag)
uv run python -m pytest
uv run python -m pytest tests/test_augmentations.py -v

# DVC pipeline
dvc repro          # run all stages
dvc pull           # fetch artifacts from remote

# Augmentation script
uv run python scripts/augment.py --src tests/fixtures --dst data/augmented/coco_train17 --ops motion_blur original

# GCP training (requires GCP_PROJECT and GCS_BUCKET env vars)
GCP_PROJECT=my-proj GCS_BUCKET=my-bucket bash scripts/gcp_train.sh
```

## Architecture

See `ARCHITECTURE.md` for program flow (data → model → training → tracking). Module
layout:

```
src/feral_vision/
  config/          # Hydra structured configs (schema.py, store.py)
  data/            # dataset loading, transforms, augmentation
                   # dataset.py        — AnnotationDataset / StreamingAnnotationDataset (PyTorch protocol only)
                   # annotations.py    — Annotation subclasses per CVTask
                   # augmentations.py  — pure albumentations, no custom Compose wrapper
                   # fetch.py          — pluggable data source dispatch (coco, local, ...)
                   # coco_to_yolo.py   — COCO polygon -> YOLO .txt converter
                   # schema_convert.py — appearance JSON -> Hydra YAML
                   # creator.py        — FeralDataset; currently broken/deprecated, do not use or fix without asking
  io_utils.py      # DatasetSource — owns all filesystem I/O for datasets
  models/          # registry.py (@register/build_model/get_model), ModelProperties.py, register_model.py
                   # sources/          — SourceAdapter subclasses per model source (HFAdapter, TorchHubAdapter, UltralyticsAdapter)
  training/        # trainer.py — canonical training entrypoint (Trainer/build_trainer)
                   # train.py          — non-canonical, do not use (see ARCHITECTURE.md)
                   # losses.py, metrics.py, optim.py
  inference/       # postprocess.py only — predictor.py removed pending redesign (see ARCHITECTURE.md)
  tasks.py         # CVTask StrEnum
conf/              # Hydra config groups: model/, train/, data/, augmentation/
  schemas/         # appearance.yaml (converted from draft_appearance_schema.json)
docker/            # Dockerfile, entrypoint.sh, USER_STEPS.md
docs/              # guide/, api/
```

## Dataset Folder Schema

All datasets use a canonical two-directory layout:

```
<root>/
  images/          # raw image files (.jpg, .jpeg, .png, .bmp)
  annotations/     # annotation files matched by stem to images/
                   #   <stem>.png or <stem>.jpg  -- semantic mask (SEG_SEMANTIC)
                   #   <stem>.txt                -- YOLO bbox (SEG_INSTANCE)
                   #   <stem>.json               -- classification labels
                   #   names.yaml                -- class index reference
```

Annotation files are dispatched by extension and assumed to already be in the
correct format for that extension — no extra validation layer.

`cfg.data.source` (`data/fetch.py`) is a pluggable dispatch point, not a fixed
enum:

- `coco` — downloads COCO train2017 (animal supercategory) via `fetch_coco()`.
- anything else — treated as a local filesystem path already in the layout above,
  via `fetch_data()`.
- additional sources are added by extending the dispatch in `fetch.py`; each must
  resolve to the layout above.

## Environment

GCP training mode requires:

- `GCP_PROJECT` — GCP project ID
- `GCS_BUCKET` — GCS bucket name for DVC remote

## Config

Never modify Hydra `default.yaml` files. Copy to a new named yaml (e.g. `trial_augmentation.yaml`) and modify the copy.
The `location` field of a required field must never be null)example:

```model/bad_example.yaml
architecture:
  location: null
```

Reason: Without an architecture location, there is no way to resolve the model. Multiple model could match the other fields. This completely negates the purpose of Hydra config files: reproducibility.

## Non-Functional Requirements

- No magic numbers in logic or config schema.
- Python == 3.12, PyTorch ≥ 2.12, CUDA 12.1.

## Documentations

Attempt to find documentation yourself. Check version with install version. If you can't find it, use context7 mcp to fetch latest documentation.

## Tool Responsibilities

Each tool owns exactly one concern — do not blur these boundaries (full detail in
`ARCHITECTURE.md` §7):

| Tool | Owns |
|---|---|
| DVC | Data only — raw/processed/augmented data artifacts. Never training/evaluation runs, checkpoints, or metrics. |
| Scripts + source code | Workflow control |
| Hydra | Parameters (all tunables live in `conf/`) |
| MLflow | Everything generated by or about a model during a training or inference run: metrics, hardware metrics, checkpoints/model artifacts, run metadata, model-version ↔ data-version link |
| `model_registry.json` | Individual model metadata (access point, API params, architecture) — static, not run-time artifacts |

Known gap: `dvc.yaml` currently declares `train`/`evaluate` stages pointing at a
deleted `pipelines` module — DVC should not own those stages per the table above;
not yet fixed.

## DVC + MLflow Integration

See memory: `reference_dvc_mlflow.md` — three patterns for linking DVC and MLflow without duplicating data. Key rule: never log raw data directories to MLflow; log `.dvc` tracker files, `dvc.api.get_url()` params, or `dvc.lock` instead.

## Pull Requests

When writing a PR description, always use `.github/PULL_REQUEST_TEMPLATE.md` as the structure. Fill in every section that is relevant to the changes. For sections that do not apply (e.g. "Reproducibility & configs" for a non-training change, or "MLflow" when no tracking was touched), do not think about them — do not include the header or placeholder text.

## SCOPING

Scope strictly to the task at hand. Do not touch anything else or expand the plan.
