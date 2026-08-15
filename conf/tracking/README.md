# Tracking configuration

## Purpose

Tracking configuration selects how a run connects to experiment tracking.

## Selection

Choose a semantic tracking variant as part of a complete Run Recipe.

For local development, start the repository-managed MLflow server with
[`scripts/tracking/start_dev_mlflow.sh`](../../scripts/tracking/start_dev_mlflow.sh)
and use the `dev` tracking variant or
`MLFLOW_TRACKING_URI=http://localhost:5000`. The server owns the local SQLite
backend and artifact directory; training clients connect to its HTTP endpoint
instead of opening the SQLite database directly.

Cloud training requires an HTTPS MLflow endpoint. The local HTTP exception is
limited to loopback hosts and is not a cloud fallback.

## Ownership

MLflow owns run-generated metrics, artifacts, checkpoints, and run metadata;
DVC owns data artifacts. The complete ownership boundary is defined in
[the program flow](../../docs/agents/program-flow.md); issue #20 owns the remaining lineage
implementation.
