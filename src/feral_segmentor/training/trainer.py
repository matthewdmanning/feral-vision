"""Training utilities shared by pipeline modules."""

from __future__ import annotations

from typing import Any, Callable

import torch

LossFn = Callable[[Any, Any], torch.Tensor]


def _try_log_metric(name: str, value: float, step: int) -> None:
    """Log a metric to MLflow only when a run is active."""
    try:
        import mlflow

        if mlflow.active_run() is not None:
            mlflow.log_metric(name, value, step=step)
    except Exception:  # pragma: no cover - logging must never break training
        pass
