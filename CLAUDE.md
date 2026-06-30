# Project Instructions

At beginning of ever session, check the operating system. Check that gh CLI is installed, git remote origin is set, and MCP servers respond, and any scripts I rely on. For each broken or missing tool, either auto-install it or give me a one-line fix. Report any missing prerequisites and stop if something is broken.

Pytest: ALWAYS use: `uv run python -m pytest` on Windows

## DVC pipeline

~~~ bash
dvc repro          # run all stages
dvc pull           # fetch artifacts from remote
~~~ bash

# Augmentation script
~~~ bash
uv run python scripts/augment.py --src tests/fixtures --dst data/augmented/coco_train17 --ops motion_blur original
~~~ bash

# GCP training (requires GCP_PROJECT and GCS_BUCKET env vars)
~~~ bash
GCP_PROJECT=my-proj GCS_BUCKET=my-bucket bash scripts/gcp_train.sh
~~~ bash
~~~

## Architecture

~~~ tree
src/feral_segmentor/
  config/          # Hydra structured configs (schema.py, store.py)
  data/            # dataset loading, transforms, augmentation
                   # creator.py       — FeralDataset (augment OR merge, not both)
                   # annotations.py   — Annotation subclasses per CVTask
                   # coco_to_yolo.py  — COCO polygon -> YOLO .txt converter
                   # schema_convert.py — appearance JSON -> Hydra YAML
  models/          # register_model.py, ModelProperties.py, sources/ (SourceAdapter base + concrete adapters)
  training/        # trainer.py, losses.py, metrics.py, optim.py, train.py
  inference/       # postprocess.py
  pipelines/       # base_segmentation_pipeline.py (entry point), evaluate_segmentation_pipeline.py
  tasks.py         # CVTask StrEnum
conf/              # Hydra config groups: model/, train/, data/, augmentation/,
                   #   gcp/, tracking/, inference/, experiment/
  schemas/         # appearance.yaml (converted from draft_appearance_schema.json)
docker/            # Dockerfile, entrypoint.sh, USER_STEPS.md
docs/              # requirements.md
~~~

## Dataset Folder Schema

All datasets use a canonical two-directory layout:

~~~ tree
<root>/
  images/          # raw image files (.jpg, .jpeg, .png, .bmp)
  annotations/     # annotation files matched by stem to images/
                   #   <stem>.png or <stem>.jpg  -- semantic mask (SEG_SEMANTIC)
                   #   <stem>.txt                -- YOLO bbox (SEG_INSTANCE)
                   #   <stem>.json               -- classification labels
                   #   names.yaml                -- class index reference
~~~

Source identifiers:

- (local, \<path>)      -- directory on disk in the layout above
- (remote, coco_2017)  -- fetched via fetch_data(), lands in data/raw/
- (remote, \<id>)       -- future sources; must resolve to the layout above

## Environment

GCP training mode requires:

- `GCP_PROJECT` — GCP project ID
- `GCS_BUCKET` — GCS bucket name for DVC remote

## Config

Never modify Hydra `default.yaml` files. Copy to a new named yaml (e.g. `trial_augmentation.yaml`) and modify the copy.

**`conf/model/`.** Model source info for architecture and weights.
**inspect()** Uses source's adapter to gather model metadata -- architecture structure and hyperparameters, model output types and structure, inputs dimensions and dtype
**register_model()**  writes info from **inspect()** to a model registry file.
**load_model_registry()** loads model registry file.

## Model Pipeline

Each model source (local file, cloud storage, online hub) has a concrete adapter
subclassing `SourceAdapter` in `src/feral_segmentor/models/sources/`.

### Model Loading

Runs as a DVC stage during training loop.

- `fetch() -> nn.Module` — load model from SOURCE.
- Weights are saved to `cfg.weights.location`. Example: `torch.save(model.state_dict(), 'model_weights.pth')`
  `cfg.weights.location=None` Weights are not saved to files.

### Model Registering

Offline/setup workflow — called prior to training loop.

- `inspect(cfg, *, fetch_if_needed=False) -> ModelProperties` — returns
  `ModelProperties(n_classes, model_outputs)`; checks model registry first. Next, uses source metadata.
  If SOURCE is a hub and `fetch_if_needed=True`, raises.
  If `fetch_if_needed=True` or SOURCE is local, the SOURCE's SourceAdapter uses `fetch()` to get an `nn.Module` then use its extracts its object properties directly or using its methods.
- `register_model(name, cfg, properties)` — writes model info to `model_registry.json`.
- `load_model_registry(name) -> ModelProperties` — reads it back.

`ModelProperties.model_outputs` is the authoritative list of what the architecture
produces (`CVTask` values, optional: bounding box, segmentation masks, logits, keypoints).

## Documentations

Attempt to find documentation yourself by web search. Verify the exact version with install version in pyproject.toml. If Use context7 mcp to fetch latest documentation.

## SCOPING

Scope strictly to the task at hand. Do NOT modify files that are not directly affected by the plan. Insert a #TODO for any dependencies or breaking changes that result from changes.
