# MLOps boundaries

Use this guide when a task spans DVC, Hydra, MLflow, source code, or the model
registry.

Scope strictly to the task at hand. See
[the tooling boundaries](../architecture/program-flow.md#7-tooling-boundaries)
for DVC, Hydra, MLflow, source-code, and model-registry ownership. Never log
raw data directories to MLflow; use DVC references or locks for data lineage.
