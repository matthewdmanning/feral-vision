"""Dependency-injected training loop.

The :class:`Trainer` is deliberately decoupled from how its collaborators are
built: it receives an already-constructed ``model``, ``optimizer``, ``loss_fn``
and (optionally) ``scheduler``. One loss-computation callable feeds the shared
optimizer loop. :func:`build_trainer` preserves existing configured callers;
run metadata and asynchronous metrics live in :mod:`.tracking`.
"""

from __future__ import annotations

import math
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from mlflow.utils.async_logging.run_operations import RunOperations

    from sightkit_learn.data.dataset import AnnotationDataset

import torch
from torch import nn

from sightkit_learn.tasks import TRAINING_TASKS
from sightkit_learn.training.execution import LossComputation, prediction_loss
from sightkit_learn.training.tracking import (
    active_mlflow_run,
    log_dataset_lineage,
    log_metrics,
    log_model,
    log_resolved_config,
)
from sightkit_learn.utils import get_logger

logger = get_logger(__name__)

DEFAULT_BEST_MODEL_PATH: str = "models/registry/best.pt"
INITIAL_BEST_LOSS: float = math.inf

LossFn = Callable[[Any, Any], torch.Tensor]


class Trainer:
    """Minimal, dependency-injected supervised training loop.

    Parameters
    ----------
    model : nn.Module
        Model to train; parameter updates remain in this loop.
    optimizer : torch.optim.Optimizer
        Optimizer instance.
    loss_fn : callable, optional
        Existing ``(outputs, targets) -> scalar`` criterion. New callers may
        instead supply ``compute_loss``. It is not used with a task adapter.
    cfg : Any
        Hydra config carrying at minimum ``cfg.train.epochs``.
    scheduler : Any, optional
        Epoch scheduler, or ReduceLROnPlateau stepped after validation.
    device : torch.device or str, optional
        Device to move model and tensors to. Defaults to CPU.
    best_model_path : str or Path, optional
        Path at which the best checkpoint is written.
    compute_loss : callable, optional
        ``(model, batch) -> (scalar total, named scalar tensors)``. Owns model
        invocation and loss computation, not backward or optimizer updates.
    input_example : optional
        Explicit MLflow-supported example, not required for native publication.
    input_example_fn : callable, optional
        Explicitly extracts an MLflow-supported example from a batch. No
        implicit model-output inspection or example extraction is performed.
    monitor : str, optional
        Named checkpoint metric. Omission preserves existing validation
        selection behavior; use a name to avoid dictionary-order dependence.
    mode : {"min", "max"}, default="min"
        Direction used to compare the checkpoint metric.
    scheduler_monitor : str, optional
        Metric for ReduceLROnPlateau; defaults to the checkpoint monitor.
    task_adapter : object, optional
        Compatibility input for existing callers; its loss is bound once to
        ``compute_loss``. New callers provide loss and collation separately.
    """

    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        loss_fn: LossFn | None = None,
        cfg: Any = None,
        scheduler: Any | None = None,
        task_adapter: Any | None = None,
        device: torch.device | str | None = None,
        best_model_path: str | Path = DEFAULT_BEST_MODEL_PATH,
        *,
        compute_loss: LossComputation | None = None,
        input_example: Any = None,
        input_example_fn: Callable[[Any], Any] | None = None,
        monitor: str | None = None,
        mode: Literal["min", "max"] = "min",
        scheduler_monitor: str | None = None,
    ) -> None:
        self.device = (
            torch.device(device) if device is not None else torch.device("cpu")
        )
        self.model = model.to(self.device)
        self.optimizer = optimizer
        self.loss_fn = loss_fn
        # Resolve legacy construction once, not in each training iteration.
        if compute_loss is None:
            if task_adapter is not None:
                compute_loss = task_adapter.loss
            else:
                from functools import partial

                if loss_fn is None:
                    raise TypeError("Provide compute_loss or loss_fn.")
                compute_loss = partial(prediction_loss, criterion=loss_fn)
        self.compute_loss = compute_loss
        self.monitor = monitor
        self.mode = mode
        self.scheduler_monitor = scheduler_monitor
        self.input_example_fn = input_example_fn
        self._epoch_metrics: dict[str, float] = {}
        self._pending_logs: list[RunOperations] = []
        self.cfg = cfg
        self.scheduler = scheduler
        self.task_adapter = task_adapter
        self.best_model_path = Path(best_model_path)
        self.best_loss = INITIAL_BEST_LOSS if mode == "min" else -math.inf
        self._input_example = input_example

    def _train_one_epoch(self, dataloader: Iterable[Any]) -> float:
        """Run one shared optimizer loop and aggregate detached loss terms."""
        self.model.train()
        totals: dict[str, torch.Tensor] = {}
        batch_count = 0
        for batch in dataloader:
            self.optimizer.zero_grad()
            loss, components = self.compute_loss(self.model, batch)
            loss.backward()
            self.optimizer.step()

            if self._input_example is None and self.input_example_fn is not None:
                self._input_example = self.input_example_fn(batch)
            for name, value in {**components, "train_loss": loss}.items():
                detached = value.detach()
                totals[name] = totals.get(name, 0) + detached
            batch_count += 1

        self._epoch_metrics = {
            name: float(value / batch_count) for name, value in totals.items()
        }
        return self._epoch_metrics.get("train_loss", INITIAL_BEST_LOSS)

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
        # Keep the previous checkpoint readable during exports or a failed save.
        with tempfile.TemporaryDirectory(
            prefix=".checkpoint-", dir=self.best_model_path.parent
        ) as temporary:
            checkpoint = Path(temporary) / "weights"
            torch.save(self.model.state_dict(), checkpoint)
            os.replace(checkpoint, self.best_model_path)

    def fit(
        self,
        dataloader: Iterable[Any],
        val_dataset: AnnotationDataset | None = None,
    ) -> dict[str, Any]:
        """Train while recording the configured MLflow run when available."""
        self._pending_logs.clear()
        with active_mlflow_run(self.cfg):
            try:
                log_resolved_config(self.cfg)
                log_dataset_lineage(self.cfg)
                history = self._fit(dataloader, val_dataset)
            finally:
                if self._pending_logs:
                    from mlflow.utils.async_logging.run_operations import (
                        get_combined_run_operations,
                    )

                    pending = get_combined_run_operations(self._pending_logs)
                    self._pending_logs.clear()
                    pending.wait()
            import mlflow
            from hydra.utils import instantiate

            if mlflow.active_run() is not None:
                model_cfg = getattr(self.cfg, "model", None)
                architecture = getattr(model_cfg, "architecture", None)
                tracking = getattr(self.cfg, "tracking", None)
                example = getattr(tracking, "input_example", None)
                log_model(
                    self.model,
                    self.best_model_path,
                    instantiate(example)
                    if example is not None
                    else self._input_example,
                    getattr(architecture, "id", None),
                    signature=instantiate(getattr(tracking, "signature", None)),
                    serialization_format=getattr(
                        tracking, "serialization_format", "pickle"
                    ),
                    name=getattr(tracking, "model_name", "pytorch_model"),
                )
            return history

    def _fit(
        self,
        dataloader: Iterable[Any],
        val_dataset: AnnotationDataset | None = None,
    ) -> dict[str, Any]:
        """Run the training loop for ``cfg.train.epochs`` epochs.

        Trains for the configured number of epochs and submits one asynchronous
        MLflow metric batch per epoch. Named monitors select scheduler and
        checkpoint measurements independently.

        Parameters
        ----------
        dataloader : Iterable
            Batched training data iterable (e.g. a ``DataLoader``).
        val_dataset : AnnotationDataset, optional
            Validation dataset passed directly to :meth:`_validate`. Set
            ``monitor`` to select a metric explicitly. When it is omitted,
            existing callers retain first-validation-metric selection, or
            training loss when validation returns no measurements.

        Returns
        -------
        dict[str, Any]
            History dict with keys ``"train_loss"`` (list), ``"best_loss"``
            (float), and any metric keys returned by ``_validate`` (lists).
        """
        epochs = int(self.cfg.train.epochs)
        history: dict[str, Any] = {"train_loss": [], "best_loss": None}

        for epoch in range(epochs):
            self._epoch_metrics = {}
            train_loss = self._train_one_epoch(dataloader)
            metrics = {**self._epoch_metrics, "train_loss": train_loss}
            validation_metrics = (
                self._validate(val_dataset) if val_dataset is not None else {}
            )
            metrics.update(validation_metrics)
            # Preserve established callers; named monitors remove ordering dependence.
            monitor = self.monitor or next(iter(validation_metrics), "train_loss")
            for name, value in metrics.items():
                history.setdefault(name, []).append(value)
                logger.info("epoch %d/%d %s=%.6f", epoch + 1, epochs, name, value)

            if self.scheduler is not None:
                if isinstance(
                    self.scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau
                ):
                    self.scheduler.step(metrics[self.scheduler_monitor or monitor])
                else:
                    self.scheduler.step()

            tracked_loss = metrics[monitor]
            improved = (
                tracked_loss < self.best_loss
                if self.mode == "min"
                else tracked_loss > self.best_loss
            )
            if improved:
                self.best_loss = tracked_loss
                self._save_best()
            operation = log_metrics(metrics, epoch)
            if operation is not None:
                self._pending_logs.append(operation)

        history["best_loss"] = self.best_loss
        return history


def build_trainer(cfg: Any) -> Trainer:
    """Build the Hydra-selected task loss and its shared Trainer collaborators.

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
    from functools import partial

    from sightkit_learn.models.register_model import model_builder
    from sightkit_learn.training.execution import (
        huggingface_loss,
        model_loss,
        ultralytics_loss,
    )
    from sightkit_learn.training.optim import (
        build_loss_fn,
        build_optimizer,
        build_scheduler,
    )

    task = TRAINING_TASKS[getattr(cfg.train, "task", "generic")]
    model = model_builder(cfg.model, task=task).to(cfg.train.device)
    optimizer = build_optimizer(model.parameters(), cfg.train.optim)
    scheduler = build_scheduler(optimizer, cfg.train.scheduler)
    execution = _loss_mode(cfg)
    task_adapter = build_task_adapter(cfg)
    loss_fn = None
    computations: dict[str, LossComputation] = {
        "model": model_loss,
        "huggingface": huggingface_loss,
        "ultralytics": ultralytics_loss,
    }
    if execution == "prediction":
        criterion = build_loss_fn(cfg.train.loss_fn)
        if isinstance(criterion, nn.Module):
            criterion = criterion.to(cfg.train.device)
        loss_fn = criterion
        compute_loss: LossComputation = partial(
            prediction_loss,
            criterion=criterion,
            aux_weight=getattr(cfg.train, "aux_weight", 0.5),
        )
    elif task_adapter is not None:
        compute_loss = task_adapter.loss
    else:
        compute_loss = computations[execution]
    return Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=loss_fn,
        compute_loss=compute_loss,
        cfg=cfg,
        scheduler=scheduler,
        task_adapter=task_adapter,
        device=cfg.train.device,
        best_model_path=getattr(cfg.train, "best_model_path", DEFAULT_BEST_MODEL_PATH),
        monitor=getattr(cfg.train, "monitor", None),
        mode=getattr(cfg.train, "mode", "min"),
        scheduler_monitor=getattr(cfg.train, "scheduler_monitor", None),
    )


def _loss_mode(cfg: Any) -> str:
    """Resolve the explicitly configured execution mode or its task/provider default."""
    mode = getattr(cfg.train, "loss_mode", "auto")
    if mode != "auto":
        return mode
    task = TRAINING_TASKS[getattr(cfg.train, "task", "generic")]
    source = cfg.model.architecture.source
    if source == "hf_hub" and task != "generic":
        return "huggingface"
    if source == "ultralytics" and task == "detection":
        return "detection_giou"
    if source == "ultralytics" and task in {
        "classification",
        "instance_segmentation",
        "pose",
    }:
        return "ultralytics"
    if task in {"detection", "instance_segmentation", "pose", "panoptic_segmentation"}:
        return "model"
    return "prediction"


def build_task_adapter(cfg: Any) -> Any | None:
    """Keep the existing detection/GIoU compatibility facade for its selected execution."""
    if _loss_mode(cfg) == "detection_giou":
        from sightkit_learn.training.task_adapters import DetectionTaskAdapter

        return DetectionTaskAdapter(num_classes=int(cfg.train.num_classes))
    return None


def build_dataloader(cfg: Any):
    """Instantiate a prepared DataLoader through Hydra, retaining the legacy source fallback.

    Parameters
    ----------
    cfg : Any
        Resolved recipe containing task, source, and optional DataLoader/collator targets.

    Returns
    -------
    DataLoader
        Loader for the selected provider's prepared batch contract.
    """
    from functools import partial

    from hydra.utils import instantiate, to_absolute_path
    from torch.utils.data import DataLoader, default_collate

    from sightkit_learn.data.batching import collate_huggingface, collate_vision
    from sightkit_learn.data.loading import instantiate_dataloader
    from sightkit_learn.training.detection import collate_detection

    mode = _loss_mode(cfg)
    collate_fn = getattr(cfg.train, "collate_fn", None)
    if collate_fn is not None:
        collate_fn = instantiate(collate_fn)
    elif mode == "detection_giou":
        collate_fn = partial(collate_detection, num_classes=int(cfg.train.num_classes))
    elif mode == "model":
        collate_fn = collate_vision
    elif mode == "huggingface":
        collate_fn = collate_huggingface
    elif mode == "ultralytics" and TRAINING_TASKS[cfg.train.task] != "classification":
        from ultralytics.data.dataset import YOLODataset

        collate_fn = YOLODataset.collate_fn
    else:
        collate_fn = default_collate

    specification = getattr(cfg.train, "dataloader", None)
    if specification is not None:
        return instantiate_dataloader(specification, collate_fn=collate_fn)

    from sightkit_learn.data.dataset import AnnotationDataset
    from sightkit_learn.io_utils import DatasetSource

    dataset = AnnotationDataset(DatasetSource(to_absolute_path(cfg.data.root)))
    return DataLoader(
        dataset,
        batch_size=cfg.train.batch_size,
        shuffle=True,
        num_workers=cfg.train.num_workers,
        collate_fn=collate_fn,
    )


def main() -> None:
    """Execute the canonical Hydra-configured training entrypoint."""
    import hydra

    from sightkit_learn.config.store import register_configs

    register_configs()

    @hydra.main(version_base=None, config_path=None, config_name=None)
    def _run(cfg: Any) -> None:
        trainer = build_trainer(cfg)
        train_loader = build_dataloader(cfg)
        trainer.fit(train_loader)

    _run()


if __name__ == "__main__":
    main()
