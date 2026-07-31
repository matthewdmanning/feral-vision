# Program Flow

This document is the canonical agent reference for how data becomes a trained
model. For cloud-service configuration, identity, and lifecycle, use
[Cloud Operations](cloudops.md); for DVC, Hydra, and MLflow ownership, use
[Tracking and Data Ownership](tracking.md).

## Data path

`data/fetch.py` selects a source that resolves to the canonical
`<root>/images/`, `<root>/annotations/` layout. Raw data lives in cloud storage
or is an always-available standard dataset. DVC owns Datasets and their Dataset
Artifacts. For cloud-prepared data, the version-aware DVC tracker and
`dataset-artifact.json` are stored beside the payload in the dataset bucket.
Cloud training follows this path:

`raw data -> GPU VM SSD -> Docker -> augmentation -> training`

The GPU VM stages selected data folders and Dataset Artifacts on its SSD, mounted
at `/data` in the container. Augmentation is a separate DVC run before training;
a shared startup script may invoke both without making them one operation.
Training receives selected folders through an environment variable. The container
does not fetch data or run DVC.

`"coco"` is one source (`fetch_coco`) among others (`"local"` via `fetch_data`
and future remote ids). The source is a dispatch point, not a fixed enum.

## Docker image flow

Docker is the workload boundary between VM SSD staging and augmentation/training.
It runs the CUDA-enabled training image with the staged data mounted at `/data`;
it does not fetch data or run DVC. Terraform and operational scripts own the
resulting cloud workload; manual Docker launches are not a supported flow.

## Annotation and dataset loading

`io_utils.DatasetSource._load_annotation` dispatches by extension to concrete
`Annotation` subclasses. Files are assumed to match their extension; malformed
files fail in the loader. `DatasetSource` owns filesystem I/O; `AnnotationDataset`
and `StreamingAnnotationDataset` implement PyTorch dataset protocols with an
injected source; `data/annotations.py` contains pure data types.

## Augmentation

`data/augmentations.py` uses stock Albumentations transforms directly, composed
from `cfg.augmentation`. There is no project-specific composition wrapper.
Augmentation previews are local-only inspection tools: they do not materialize a
Dataset Variant, participate in DVC, or affect cloud training.

## Model acquisition

Each external model source has a `SourceAdapter` in `models/sources/`; in-repo
architectures register through `models/register_model.py`. Architecture and
weights are independent configuration branches. The MLflow Model Registry stores
named model configuration and inspected properties; an offline journal is only a
temporary retry buffer.

## Training

`training/trainer.py` is the canonical training path. `build_trainer(cfg)` wires
the model, optimizer, scheduler, and loss. The trainer logs metrics when an
MLflow run is active, writes a local best checkpoint, and attempts to log only
the selected best model artifact. Loss selection is configuration-driven;
`segmentation_loss` and distillation are not canonical behavior.

## Tool ownership

| Tool | Owns |
|---|---|
| DVC | Raw, processed, and augmented Datasets and Dataset Artifacts; never training/evaluation runs, checkpoints, or metrics. |
| MLflow | Run metrics, artifacts, checkpoints, metadata, and model-version-to-Dataset-Artifact links. |
| Scripts / source code | Workflow control. |
| Hydra | Tunable configuration in `conf/`. |
| MLflow Model Registry | Registered Models; its offline journal is a retry buffer only. |
