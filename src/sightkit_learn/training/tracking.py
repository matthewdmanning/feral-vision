"""Run metadata and native asynchronous MLflow metric submission."""

from __future__ import annotations

import copy
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Iterator, cast

import torch
from torch import nn

if TYPE_CHECKING:
    from mlflow.utils.async_logging.run_operations import RunOperations


def log_resolved_config(cfg: Any) -> None:
    """Store the exact resolved Run Recipe in an active MLflow run."""
    import mlflow
    from omegaconf import OmegaConf

    if mlflow.active_run() is not None:
        resolved = cast(
            dict[str, Any],
            OmegaConf.to_container(
                cfg, resolve=True, throw_on_missing=True, enum_to_str=True
            ),
        )
        mlflow.log_dict(resolved, "run_config/resolved_config.json")


def log_metrics(metrics: dict[str, float], step: int) -> RunOperations | None:
    """Submit epoch metrics asynchronously to the active run.

    Parameters
    ----------
    metrics : dict[str, float]
        Detached epoch totals and validation measurements.
    step : int
        Epoch index.

    Returns
    -------
    RunOperations or None
        Completion handle, or None when no run is active.
    """
    import mlflow

    if mlflow.active_run() is not None:
        return mlflow.log_metrics(metrics, step=step, synchronous=False)
    return None


def _dataset_artifact_manifest_path(cfg: Any) -> Path | None:
    """Resolve the upstream Dataset Artifact manifest consumed by training."""
    configured_path = os.environ.get("DATASET_ARTIFACT_MANIFEST")
    if configured_path:
        return Path(configured_path)

    data_root = getattr(getattr(cfg, "data", None), "root", None)
    if data_root:
        return Path(str(data_root)) / "dataset-artifact.json"
    return None


def log_dataset_lineage(cfg: Any) -> None:
    """Record the exact upstream Dataset Artifact manifest in an active MLflow run."""
    import mlflow

    manifest_path = _dataset_artifact_manifest_path(cfg)
    if (
        mlflow.active_run() is None
        or manifest_path is None
        or not manifest_path.is_file()
    ):
        return

    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    expected_digest = os.environ.get("DATASET_ARTIFACT_SHA256")
    if expected_digest and digest != expected_digest:
        raise ValueError(
            "dataset-artifact.json changed after deployment validation: "
            f"expected {expected_digest}, got {digest}"
        )

    mlflow.log_param("dataset_artifact_sha256", digest)
    dataset_artifact_uri = os.environ.get("DATASET_ARTIFACT_URI")
    if dataset_artifact_uri:
        mlflow.log_param("dataset_artifact_uri", dataset_artifact_uri)
    mlflow.log_artifact(str(manifest_path), artifact_path="data_lineage")


@contextmanager
def active_mlflow_run(cfg: Any) -> Iterator[None]:
    """Reuse an active run or start one when tracking is configured."""
    tracking = getattr(cfg, "tracking", None)
    if tracking is None:
        yield
        return

    import mlflow

    if mlflow.active_run() is not None:
        yield
        return

    tracking_uri = getattr(tracking, "tracking_uri", None)
    experiment_name = getattr(tracking, "experiment_name", None)
    if tracking_uri is not None:
        mlflow.set_tracking_uri(tracking_uri)
    if experiment_name is not None:
        mlflow.set_experiment(experiment_name)
    run = mlflow.start_run()

    with run:
        external_run_id = os.environ.get("FERAL_VISION_RUN_ID")
        if external_run_id:
            mlflow.set_tag("feral_vision_run_id", external_run_id)
        yield


def log_model(
    model: nn.Module,
    checkpoint_path: Path,
    input_example: Any = None,
    registered_model_name: str | None = None,
    *,
    signature: Any = None,
    serialization_format: str = "pickle",
    name: str = "pytorch_model",
) -> Any:
    """Publish selected weights while restoring the caller's model state.

    Parameters
    ----------
    model : nn.Module
        Model whose selected weights will be recorded.
    checkpoint_path : Path
        Checkpoint containing the selected state dictionary.
    input_example : optional
        An explicit MLflow-supported input example; not required for pickle serialization.
    registered_model_name : str or None
        Optional identity under which to register the logged model.
    signature : optional
        MLflow signature, passed through without project inference or output conversion.
    serialization_format : str
        MLflow PyTorch serialization format, selected by Hydra.
    name : str
        Name of the logged model within the run.

    Returns
    -------
    ModelInfo
        Native MLflow publication and registration metadata.
    """
    import mlflow

    current_state = copy.deepcopy(model.state_dict())
    was_training = model.training
    training_modes = [(module, module.training) for module in model.modules()]
    try:
        best_state = torch.load(
            checkpoint_path,
            map_location=next(model.parameters()).device,
            weights_only=True,
        )
        model.load_state_dict(best_state)
        model.eval()
        info = mlflow.pytorch.log_model(
            model,
            name=name,
            serialization_format=serialization_format,
            signature=signature,
            input_example=input_example,
            registered_model_name=registered_model_name,
        )
        if registered_model_name:
            mlflow.set_tag("registered_model_name", registered_model_name)
            mlflow.set_tag("model_version", info.registered_model_version)
        return info

    finally:
        model.load_state_dict(current_state)
        model.train(was_training)
        for module, training in training_modes:
            module.training = training
