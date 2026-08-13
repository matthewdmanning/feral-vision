# Program Flow

## Cloud Flows

### Data Sets

`Data Source Adapter -> request -> optional transform or format -> Dataset`

`Dataset -> modification -> Dataset Variant`

`Dataset or Dataset Variant -> Publish -> DVC Registry`

A Dataset Variant is a subclass of Dataset.

### Models

`Model Source Adapter -> model (+ optional weights)`

### Cloud Builds

`Run Recipe (model + data) -> Cloud Run -> MLflow metrics and SQLite entries + best-performing model weights (Model Artifact) in Google Storage`

The data and model flows are independent and may be composed in the same Cloud
Run.
Cloud Operations provides the execution environment; it does not change the
pipeline's meaning.

DVC owns Dataset Artifacts and their lineage. Hydra owns Run Recipes.
Terraform owns Cloud Resource lifecycle. MLflow owns training evidence; it does
not receive raw dataset directories. [Cloud Operations](cloudops.md) ·
[Configuration](configuration.md) · [Training guide](../guide/training.rst)
