# Tracking configuration

Tracking configuration selects how a run connects to experiment tracking.
MLflow owns run-generated metrics, artifacts, checkpoints, and run metadata;
DVC owns data artifacts. The complete ownership boundary is canonical in
[ARCHITECTURE.md](../../ARCHITECTURE.md).

Choose a semantic tracking variant as part of a complete run. Do not use this
documentation to define MLflow artifact lineage or duplicate the work tracked
by issue #20.
