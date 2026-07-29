# Tracking and Data Ownership

Use this guide when a task spans DVC, Hydra, MLflow, source code, or the model
registry.

See [tool ownership](program-flow.md#tool-ownership) for the canonical boundary.
DVC owns Datasets and Dataset Artifacts; MLflow owns run metrics, artifacts,
checkpoints, metadata, and model-version links. Hydra owns tunables in `conf/`.
Never log raw data directories to MLflow; use a Dataset Artifact for Data
Lineage.
