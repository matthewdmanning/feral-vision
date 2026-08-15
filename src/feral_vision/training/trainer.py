"""Dependency-injected training loop.

The :class:`Trainer` is deliberately decoupled from how its collaborators are
built: it receives an already-constructed ``model``, ``optimizer``, ``loss_fn``
and (optionally) ``scheduler``. This keeps the loop trivially unit-testable with
dummies. :func:`build_trainer` wires the *real* collaborators from the other
units and is exercised by the canonical training entrypoint (:func:`main`).
"""

from __future__ import annotations

import copy
import hashlib
import math
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable, Iterator

if TYPE_CHECKING:
    from feral_vision.data.dataset import AnnotationDataset

import torch
from torch import nn

from feral_vision.tracking import validate_tracking_uri
from feral_vision.utils import get_logger

logger = get_logger(__name__)

DEFAULT_BEST_MODEL_PATH: str = "models/registry/best.pt"
INITIAL_BEST_LOSS: float = math.inf
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DVC_PIPELINE_PATH = _PROJECT_ROOT / "dvc.yaml"

LossFn = Callable[[Any, Any], torch.Tensor]


def _artifact_name_component(value: Any, fallback: str = "unknown") -> str:
    """Convert config text into a stable MLflow artifact-name component."""
    text = str(value).strip()
    if not text:
        return fallback
    component = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.")
    return component or fallback


def _model_artifact_name(cfg: Any) -> str:
    """Build a descriptive MLflow model artifact name from the Run Recipe."""
    model_cfg = getattr(cfg, "model", None)
    architecture = getattr(model_cfg, "architecture", None)
    architecture_id = _artifact_name_component(
        getattr(architecture, "id", None), fallback="model"
    )

    data_cfg = getattr(cfg, "data", None)
    data_source = getattr(data_cfg, "source", None)
    data_root = getattr(data_cfg, "root", None)
    dataset_values = (data_source, Path(str(data_root)).name if data_root else None)
    dataset_parts = [
        _artifact_name_component(value) for value in dataset_values if value
    ]

    parts = [architecture_id]
    if dataset_parts:
        parts.append(f"dataset-{'-'.join(dataset_parts)}")

    augmentation = getattr(getattr(cfg, "augmentation", None), "name", None)
    if augmentation:
        parts.append(f"augmentation-{_artifact_name_component(augmentation)}")

    epochs = getattr(getattr(cfg, "train", None), "epochs", None)
    if epochs is not None:
        parts.append(f"epochs-{_artifact_name_component(epochs)}")
    return "__".join(parts)


def _resolved_config(cfg: Any) -> Any:
    """Convert a Hydra config or lightweight config object into JSON-safe data."""
    try:
        from omegaconf import OmegaConf

        if OmegaConf.is_config(cfg):
            return OmegaConf.to_container(cfg, resolve=True, throw_on_missing=True)
    except ImportError:  # pragma: no cover - OmegaConf is a project dependency
        pass

    if isinstance(cfg, dict):
        return {key: _resolved_config(value) for key, value in cfg.items()}
    if isinstance(cfg, (list, tuple)):
        return [_resolved_config(value) for value in cfg]
    if hasattr(cfg, "__dict__"):
        return {key: _resolved_config(value) for key, value in vars(cfg).items()}
    if isinstance(cfg, Path):
        return str(cfg)
    return cfg


def _try_log_resolved_config(cfg: Any) -> None:
    """Store the exact resolved Run Recipe in an active MLflow run."""
    import mlflow

    if mlflow.active_run() is None:
        raise RuntimeError("MLflow run is required before logging the Run Recipe")
    mlflow.log_dict(_resolved_config(cfg), "run_config/resolved_config.json")


def _try_log_metric(name: str, value: float, step: int) -> None:
    """Log a single metric to MLflow when a run is active.

    Parameters
    ----------
    name : str
        Metric name as it will appear in MLflow.
    value : float
        Metric value for the current step.
    step : int
        Training step (typically the epoch index).
    """
    import mlflow

    if mlflow.active_run() is None:
        raise RuntimeError("MLflow run is required before logging metrics")
    mlflow.log_metric(name, value, step=step)


def _dvc_data_version(tracker_path: Path) -> str:
    """Identify a staged DVC tracker without running DVC."""
    if tracker_path.name in {"data.dvc", "dvc.lock"}:
        digest = hashlib.sha256(tracker_path.read_bytes()).hexdigest()
        return f"{tracker_path.name}@sha256:{digest}"

    try:
        commit = subprocess.check_output(
            ["git", "-C", str(_PROJECT_ROOT), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        return f"dvc.yaml@{commit}"
    except (OSError, subprocess.CalledProcessError):
        digest = hashlib.sha256(_DVC_PIPELINE_PATH.read_bytes()).hexdigest()
        return f"dvc.yaml@sha256:{digest}"


def _try_log_dvc_lineage(cfg: Any) -> None:
    """Record the DVC pipeline metadata and tracker file in an active MLflow run."""
    import mlflow

    if mlflow.active_run() is None:
        raise RuntimeError("MLflow run is required before logging DVC lineage")
    data_root = getattr(getattr(cfg, "data", None), "root", None)
    if not data_root:
        raise RuntimeError("training data root is required for DVC lineage")
    tracker_path = Path(str(data_root)) / "dvc.lock"
    if not tracker_path.exists():
        raise FileNotFoundError(f"required DVC lockfile is missing: {tracker_path}")
    mlflow.log_param("dvc_data_version", _dvc_data_version(tracker_path))
    mlflow.log_artifact(str(tracker_path), artifact_path="data_lineage")


@contextmanager
def _active_mlflow_run(cfg: Any) -> Iterator[None]:
    """Start the required HTTPS MLflow run for the training process."""
    tracking = getattr(cfg, "tracking", None)
    if tracking is None:
        raise RuntimeError("MLflow tracking configuration is required")

    import mlflow

    tracking_uri = getattr(tracking, "tracking_uri", None)
    if not isinstance(tracking_uri, str):
        raise ValueError("MLflow tracking_uri must be a string")
    validate_tracking_uri(tracking_uri)
    mlflow.set_tracking_uri(tracking_uri)

    experiment_name = getattr(tracking, "experiment_name", None)
    if not isinstance(experiment_name, str) or not experiment_name:
        raise ValueError("MLflow experiment_name is required")
    mlflow.set_experiment(experiment_name)
    if mlflow.active_run() is not None:
        yield
        return
    run = mlflow.start_run()

    with run:
        yield


class Trainer:
    """Minimal, dependency-injected supervised training loop.

    Parameters
    ----------
    model : nn.Module
        Model to train.
    optimizer : torch.optim.Optimizer
        Optimizer instance.
    loss_fn : LossFn
        Callable ``(outputs, targets) -> scalar tensor``.
    cfg : Any
        Hydra config carrying at minimum ``cfg.train.epochs``.
    scheduler : Any, optional
        Learning-rate scheduler with a ``step()`` method.
    device : torch.device or str, optional
        Device to move model and tensors to. Defaults to CPU.
    best_model_path : str or Path, optional
        Path at which the best checkpoint is written.
    """

    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        loss_fn: LossFn,
        cfg: Any,
        scheduler: Any | None = None,
        task_adapter: Any | None = None,
        device: torch.device | str | None = None,
        best_model_path: str | Path = DEFAULT_BEST_MODEL_PATH,
    ) -> None:
        self.device = (
            torch.device(device) if device is not None else torch.device("cpu")
        )
        self.model = model.to(self.device)
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        self.cfg = cfg
        self.scheduler = scheduler
        self.task_adapter = task_adapter
        self.best_model_path = Path(best_model_path)
        self.best_loss = INITIAL_BEST_LOSS
        self._input_example: torch.Tensor | None = None

    def _move(self, tensor: Any) -> Any:
        return tensor.to(self.device) if isinstance(tensor, torch.Tensor) else tensor

    def _train_one_epoch(self, dataloader: Iterable[Any]) -> float:
        self.model.train()
        running_loss = 0.0
        batch_count = 0
        for batch in dataloader:
            self.optimizer.zero_grad()
            if self.task_adapter is None:
                inputs, targets = batch
                inputs = self._move(inputs)
                targets = self._move(targets)
                if self._input_example is None:
                    self._input_example = inputs.detach().cpu()
                outputs = self.model(inputs)
                loss = self.loss_fn(outputs, targets)
            else:
                loss, _ = self.task_adapter.loss(self.model, batch)
                if self._input_example is None:
                    self._input_example = batch.images.detach().cpu()
            loss.backward()
            self.optimizer.step()

            running_loss += float(loss.item())
            batch_count += 1

        if self.scheduler is not None:
            self.scheduler.step()

        return running_loss / batch_count if batch_count else INITIAL_BEST_LOSS

    @torch.no_grad()
    def _validate(self, dataset: AnnotationDataset) -> dict[str, float]:
        """Compute validation metrics over a dataset.

        The base implementation returns an empty dict. Subclasses override this
        method to run per-sample inference and return task-specific metrics
        (e.g. IoU, Dice). The returned dict is logged to MLflow and used to
        select the best checkpoint in :meth:`fit`.

        Parameters
        ----------
        dataset : AnnotationDataset
            Validation dataset. Samples are loaded one at a time — no
            DataLoader or batching is expected.

        Returns
        -------
        dict[str, float]
            Metric name → value pairs. Empty dict in the base implementation.
        """
        return {}

    def _save_best(self) -> None:
        self.best_model_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), self.best_model_path)

    def _try_log_model(self, model_name: str) -> None:
        """Log only the selected best model to the active MLflow run."""
        if self._input_example is None or not self.best_model_path.exists():
            raise RuntimeError(
                "best model checkpoint and input example are required for MLflow logging"
            )

        import mlflow
        from mlflow.pytorch import log_model
        from mlflow.models import infer_signature

        active_run = mlflow.active_run()
        if active_run is None:
            raise RuntimeError("MLflow run is required before logging the model")

        current_state = copy.deepcopy(self.model.state_dict())
        was_training = self.model.training
        try:
            best_state = torch.load(
                self.best_model_path, map_location=self.device, weights_only=True
            )
            self.model.load_state_dict(best_state)
            input_example = self._input_example.numpy()
            self.model.eval()
            with torch.no_grad():
                predictions = self.model(self._move(self._input_example))
            signature = infer_signature(
                input_example, predictions.detach().cpu().numpy()
            )
            log_model(
                self.model,
                name=model_name,
                signature=signature,
                input_example=input_example,
            )
            model_cfg = getattr(self.cfg, "model", None)
            architecture = getattr(model_cfg, "architecture", None)
            registered_model_name = getattr(architecture, "id", None)
            if registered_model_name:
                model_version = mlflow.register_model(
                    model_uri=f"runs:/{active_run.info.run_id}/{model_name}",
                    name=registered_model_name,
                )
                mlflow.set_tag("registered_model_name", registered_model_name)
                mlflow.set_tag("model_version", model_version.version)
        finally:
            self.model.load_state_dict(current_state)
            self.model.train(was_training)

    def fit(
        self,
        dataloader: Iterable[Any],
        val_dataset: AnnotationDataset | None = None,
    ) -> dict[str, Any]:
        """Train while recording the required configured MLflow run."""
        with _active_mlflow_run(self.cfg):
            _try_log_resolved_config(self.cfg)
            _try_log_dvc_lineage(self.cfg)
            history = self._fit(dataloader, val_dataset)
            self._try_log_model(_model_artifact_name(self.cfg))
            return history

    def _fit(
        self,
        dataloader: Iterable[Any],
        val_dataset: AnnotationDataset | None = None,
    ) -> dict[str, Any]:
        """Run the training loop for ``cfg.train.epochs`` epochs.

        Trains for the configured number of epochs, logging each metric to
        MLflow via :func:`_try_log_metric`. When ``val_dataset`` is provided,
        :meth:`_validate` is called each epoch and its returned metrics are
        used to select the best checkpoint; otherwise train loss is used.

        Parameters
        ----------
        dataloader : Iterable
            Batched training data iterable (e.g. a ``DataLoader``).
        val_dataset : AnnotationDataset, optional
            Validation dataset passed directly to :meth:`_validate`. When
            provided, the first metric value returned by ``_validate``
            determines checkpoint selection; train loss is used as fallback
            when ``_validate`` returns an empty dict.

        Returns
        -------
        dict[str, Any]
            History dict with keys ``"train_loss"`` (list), ``"best_loss"``
            (float), and any metric keys returned by ``_validate`` (lists).
        """
        epochs = int(self.cfg.train.epochs)
        history: dict[str, Any] = {"train_loss": [], "best_loss": None}

        for epoch in range(epochs):
            train_loss = self._train_one_epoch(dataloader)
            history["train_loss"].append(train_loss)
            _try_log_metric("train_loss", train_loss, epoch)
            logger.info("epoch %d/%d train_loss=%.6f", epoch + 1, epochs, train_loss)

            tracked_loss = train_loss
            if val_dataset is not None:
                metrics = self._validate(val_dataset)
                for name, value in metrics.items():
                    history.setdefault(name, []).append(value)
                    _try_log_metric(name, value, epoch)
                    logger.info("epoch %d/%d %s=%.6f", epoch + 1, epochs, name, value)
                if metrics:
                    tracked_loss = next(iter(metrics.values()))

            if tracked_loss < self.best_loss:
                self.best_loss = tracked_loss
                self._save_best()

        history["best_loss"] = self.best_loss
        return history


def build_trainer(cfg: Any) -> Trainer:
    """Use this function to wire a :class:`Trainer` with real collaborators from other units.

    Imports are local so this module imports cleanly even while collaborators
    are skeletons; the canonical training entrypoint calls this function.

    Parameters
    ----------
    cfg : Any
        Hydra config carrying ``cfg.model``, ``cfg.train.optim``,
        ``cfg.train.scheduler``, ``cfg.train.loss_fn``, and ``cfg.train.device``.

    Returns
    -------
    Trainer
        Fully wired trainer ready to call :meth:`~Trainer.fit`.
    """
    from feral_vision.models.register_model import model_builder
    from feral_vision.training.optim import (
        build_loss_fn,
        build_optimizer,
        build_scheduler,
    )

    model = model_builder(cfg.model)
    optimizer = build_optimizer(model.parameters(), cfg.train.optim)
    scheduler = build_scheduler(optimizer, cfg.train.scheduler)
    loss_fn = build_loss_fn(cfg.train.loss_fn)
    task_adapter = build_task_adapter(cfg)

    return Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=loss_fn,
        cfg=cfg,
        scheduler=scheduler,
        task_adapter=task_adapter,
        device=cfg.train.device,
    )


def build_task_adapter(cfg: Any) -> Any | None:
    """Use this function when a Run Recipe selects task-specific trainer behavior."""
    task = getattr(cfg.train, "task", "generic")
    if task == "generic":
        return None
    if task == "detection":
        from feral_vision.training.task_adapters import DetectionTaskAdapter

        return DetectionTaskAdapter(num_classes=int(cfg.train.num_classes))
    raise ValueError(f"unsupported training task {task!r}")


def main() -> None:
    """Execute the canonical Hydra-configured training entrypoint."""
    import hydra
    from hydra.utils import to_absolute_path

    from feral_vision.config.store import register_configs

    register_configs()

    @hydra.main(
        version_base=None, config_path="../../../conf", config_name="runs/baseline"
    )
    def _run(cfg: Any) -> None:
        from torch.utils.data import DataLoader

        from feral_vision.data.dataset import AnnotationDataset
        from feral_vision.io_utils import DatasetSource

        train_dataset = AnnotationDataset(
            DatasetSource(to_absolute_path(cfg.data.root))
        )
        trainer = build_trainer(cfg)
        train_loader = DataLoader(
            train_dataset,
            batch_size=cfg.train.batch_size,
            shuffle=True,
            num_workers=cfg.train.num_workers,
            collate_fn=(
                trainer.task_adapter.collate
                if trainer.task_adapter is not None
                else None
            ),
        )
        trainer.fit(train_loader)

    _run()


if __name__ == "__main__":
    main()
