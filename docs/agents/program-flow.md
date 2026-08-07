# Program Flow

## Data Flow

`Dataset -> optional modification -> DVC Registry`

[Data and ingestion](data.md)

## Model Sourcing

`Model source -> Model Source Adapter -> model (+ optional weights)`

[Model API](../api/models.rst) · [Coding standards](coding-standards.md)

## Cloud Runs (Training)

`Terraform -> provisioned Cloud Resources`

`Data + Model + Run Recipe + provisioned Cloud Resources -> Cloud Training Run -> Run Record + Model Artifact`

[Cloud Operations](cloudops.md) · [Configuration](configuration.md) · [Training guide](../guide/training.rst) · [Tracking and Data Integration](tracking.md)
