# MLOps boundaries

Use this guide when a task spans DVC, Hydra, MLflow, source code, or the model
registry.

 The execution data-to-model flow is in [Program Flow](program-flow.md).

Scope strictly to the task at hand. See
[the tooling boundaries](program-flow.md#tool-ownership)
for DVC, Hydra, MLflow, source-code, and model-registry ownership. Never log
raw data directories to MLflow; use a Dataset Artifact for Data Lineage.


## Cloud Dataset Artifacts

### Storage structure

```text
Cloud Storage
├── dataset-only bucket                 # one bucket per environment
│   └── datasets/<dataset>/<artifact>/
│       ├── payload/
│       │   ├── images/
│       │   └── annotations/
│       ├── dataset-artifact.json
│       └── dataset-artifact.dvc
└── general storage
    ├── Terraform state + Cloud Build staging
    ├── MLflow artifacts
    └── non-dataset operational assets
```
