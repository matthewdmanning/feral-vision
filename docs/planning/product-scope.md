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

- Data operations, including acquisition and augmentation, must be idempotent
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
  mounted in the container at `/data`.
- Bucket names, project IDs, and instance settings are supplied at runtime via
  environment variables or `gcloud`, never baked into the image.
- MLflow is deployed as a shared Cloud Run service. Its backend store is a
  Cloud SQL PostgreSQL database and its artifact store is a GCS bucket. The
  training container receives the Cloud Run tracking URI; it does not start a
  local MLflow server or copy a SQLite database to GCS. Per the
  [tooling boundary](../architecture/program-flow.md#7-tooling-boundaries), run-generated
  model artifacts belong to MLflow. When artifact logging succeeds, only the
  selected best model artifact is recorded in its configured GCS prefix; do not
  upload intermediate checkpoints to a parallel GCS location directly.

This is a required deployment topology, not evidence that a first cloud run is
ready. Before the first production run, the package must produce the readiness
and preflight evidence in [issue #37](https://github.com/matthewdmanning/feral-vision/issues/37),
the phase-aware recovery and final summary in [issue #38](https://github.com/matthewdmanning/feral-vision/issues/38),
and the complete model-artifact and lineage behavior in
[issue #20](https://github.com/matthewdmanning/feral-vision/issues/20). Until
then, the Docker procedure is an implementation path, not a first-run
acceptance runbook.

## Non-functional constraints

- Local development may continue when no MLflow server is active; metric logging
  is a no-op in that case. First cloud-run acceptance requires durable MLflow
  evidence as stated above.
