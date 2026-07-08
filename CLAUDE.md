# Project Instructions

At beginning of session, check that gh CLI is installed, git remote origin is set, and MCP servers respond, and any scripts I rely on. For each broken or missing tool, either auto-install it or give me a one-line fix. Report any missing prerequisites and stop if something is broken.



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

```
src/feral_segmentor/
  config/          # Hydra structured configs (schema.py, store.py)
  data/            # dataset loading, transforms, augmentation
                   # creator.py       — FeralDataset (augment OR merge, not both)
                   # annotations.py   — Annotation subclasses per CVTask
                   # coco_to_yolo.py  — COCO polygon -> YOLO .txt converter
                   # schema_convert.py — appearance JSON -> Hydra YAML
  models/          # teacher.py (YOLO), segmentation.py, registry (ModelProfile)
  training/        # trainer.py, losses.py, metrics.py, optim.py, train.py
  inference/       # predictor
  tasks.py         # CVTask StrEnum
conf/              # Hydra config groups: model/, train/, data/, augmentation/
  schemas/         # appearance.yaml (converted from draft_appearance_schema.json)
docker/            # Dockerfile, entrypoint.sh, USER_STEPS.md
docs/              # requirements.md
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

Source identifiers:
- (local, <path>)      -- directory on disk in the layout above
- (remote, coco_2017)  -- fetched via fetch_coco(), lands in data/raw/
- (remote, <id>)       -- future sources; must resolve to the layout above

## Environment

GCP training mode requires:
- `GCP_PROJECT` — GCP project ID
- `GCS_BUCKET` — GCS bucket name for DVC remote

## Config

Never modify Hydra `default.yaml` files. Copy to a new named yaml (e.g. `trial_augmentation.yaml`) and modify the copy.

## Documentations



Attempt to find documentation yourself. Check version with install version. If you can't find it, use context7 mcp to fetch latest documentation.

## Pull Requests

When writing a PR description, always use `.github/PULL_REQUEST_TEMPLATE.md` as the structure. Fill in every section that is relevant to the changes. For sections that do not apply (e.g. "Reproducibility & configs" for a non-training change, or "MLflow" when no tracking was touched), do not think about them — do not include the header or placeholder text.

## SCOPING

Scope strictly to the task at hand. Do not touch anything else or expand the plan.
