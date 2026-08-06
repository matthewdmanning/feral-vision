# Program Flow

## Shared architecture

`Dataset -> optional modification -> Dataset Variant -> DVC Registry`

`Model source -> Model Source Adapter -> model (+ optional weights)`

`Terraform -> provisioned Cloud Resources`

`immutable Dataset Variant + digest-pinned model image + Run Recipe + Cloud Resources -> Cloud Training Run -> Run Record + Model Artifact`

DVC owns Dataset Artifacts and their lineage. Hydra owns Run Recipe selection.
Terraform owns Cloud Resource lifecycle. MLflow owns training evidence; it does
not receive raw dataset directories. [Data and ingestion](data.md) · [Cloud
Operations](cloudops.md) · [Configuration](configuration.md) · [Tracking and
Data Integration](tracking.md)

## First augmented detection baseline

The concrete `first_run_augmented` topology is a Cloud Build materialization
followed by a planned private GPU VM run. The VM hosts the run-local MLflow
endpoint, exports durable evidence to a non-dataset artifact prefix, and is
disposable. The detailed decision, identity boundary, and acceptance evidence
are in [ADR 0002](../adr/0002-first-augmented-detection-cloud-run.md); the
operator inputs and commands are in the [run contract](../runs/first-detection-baseline-first_run_augmented.md).

[Model API](../api/models.rst) · [Implementation workflow](implementation.md) · [Training guide](../guide/training.rst)
