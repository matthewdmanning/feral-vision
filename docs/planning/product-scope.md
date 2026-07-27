# Product Scope and Delivery Constraints

This document is the canonical planning source for Feral Vision's product
scope and delivery constraints. For the data-to-model program flow and tool
ownership, see [the program flow](../architecture/program-flow.md).

## Product scope

Feral Vision detects and instance-segments feral cats in images captured on
mobile devices. Its output is a pixel-level instance mask for each detected
cat, supporting downstream tracking, population monitoring, and
trap-neuter-return (TNR) work.

The following are out of scope:

- Real-time video inference.
- Active learning or human-in-the-loop labelling.
- Multi-GPU or distributed training.
- A model-serving API.

## Data and configuration constraints

- DVC runs, including acquisition and augmentation, must be idempotent
  and re-runnable; fetching skips files already present.
- A train/validation split must be static, use seed `42`, expose its ratio
  through Hydra, and be persisted to GCS before training begins.
- Hydra, rather than code changes, controls data source, data root, image
  size, validation-split ratio, class-similarity weights, and training
  hyperparameters.
- Augmentation uses stock Albumentations transforms only; no project-specific
  composition wrapper is permitted. Its active operations are declared through
  Hydra.
- Model architecture and optional weights are declared in Hydra. Weight sources
  may be local, remote, or a PyTorch Hub entrypoint.
- MLflow records training metrics whenever a tracking run is active.

## Cloud-training delivery contract

- Production training targets Docker on a GCE GPU instance. GitHub Actions is
  validation-only. The production image is stored in Google Artifact Registry.
- GCP access uses the instance service account through Workload Identity; do
  not use service-account key files.
- Before training, input data is synchronized from GCS to the attached SSD,
  mounted in the container at `/data`; the configured Hydra augmentation runs on
  the GPU VM before the trainer starts.
- Bucket names, project IDs, and instance settings are declared in the
  cloud-smoke configuration and passed at runtime; they are never baked into
  the image.
- MLflow uses a database URI generated for each run. It is not a shared,
  persistent hosted service, so do not provision Cloud Run or Cloud SQL for a
  smoke test. Per the [tooling boundary](../architecture/program-flow.md#7-tooling-boundaries),
  MLflow still owns any run-generated model artifacts; do not create a parallel
  checkpoint-export path.

The first cloud run is an empirical manual smoke. It is not gated on preflight,
a reusable launcher, recovery infrastructure, or complete model-lineage work.
Record the command, inputs, logs, result, and observed blockers in
[issue #38](https://github.com/matthewdmanning/feral-vision/issues/38); decide
what to automate only after that evidence exists.

## Non-functional constraints

- Local development may continue when no MLflow run is active; metric logging is
  a no-op in that case. Persistence beyond an individual run is a later decision,
  not a smoke-test requirement.
