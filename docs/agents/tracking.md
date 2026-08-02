# Tracking and Data Integration

Use this guide when implementing tracking or data-integration behavior that
crosses DVC, Hydra, MLflow, source code, or the model registry.

Never log raw data directories to MLflow; use a Dataset Artifact for Data
Lineage.
