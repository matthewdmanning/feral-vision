"""Dependency-injected training loop.

The :class:`Trainer` is deliberately decoupled from how its collaborators are
built: it receives an already-constructed ``model``, ``optimizer``, ``loss_fn``
and (optionally) ``scheduler``. This keeps the loop trivially unit-testable with
dummies. :func:`build_trainer` wires the *real* collaborators from the other
units and is the only path that imports them; it is exercised by the DVC
``train`` stage entrypoint (:func:`main`), never by the trainer's own tests.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterable

if TYPE_CHECKING:
    from feral_vision.data.dataset import AnnotationDataset

import torch
from torch import nn

from feral_vision.utils import get_logger

logger = get_logger(__name__)

DEFAULT_BEST_MODEL_PATH: str = "models/registry/best.pt"
INITIAL_BEST_LOSS: float = math.inf

LossFn = Callable[[Any, Any], torch.Tensor]


def _try_log_metric(name: str, value: float, step: int) -> None:
    """Use this function to log a single metric to MLflow when a run is active.

    Guarded so the trainer never requires a running tracking server: if mlflow
    is unavailable or no run is active, logging is silently skipped.

    Parameters
    ----------
    name : str
        Metric name as it will appear in MLflow.
    value : float
        Metric value for the current step.
    step : int
        Training step (typically the epoch index).
    """
    try:
        import mlflow

        if mlflow.active_run() is not None:
            mlflow.log_metric(name, value, step=step)
    except Exception:  # pragma: no cover - logging must never break training
        pass


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
        self.best_model_path = Path(best_model_path)
        self.best_loss = INITIAL_BEST_LOSS

    def _move(self, tensor: Any) -> Any:
        return tensor.to(self.device) if isinstance(tensor, torch.Tensor) else tensor

    def _train_one_epoch(self, dataloader: Iterable[Any]) -> float:
        self.model.train()
        running_loss = 0.0
        batch_count = 0
        for inputs, targets in dataloader:
            inputs = self._move(inputs)
            targets = self._move(targets)

            self.optimizer.zero_grad()
            outputs = self.model(inputs)
            loss = self.loss_fn(outputs, targets)
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

    def fit(
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
    are skeletons; ``build_trainer`` is only called from the DVC entrypoint.

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

    return Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=loss_fn,
        cfg=cfg,
        scheduler=scheduler,
        device=cfg.train.device,
    )


def main() -> None:
    """DVC ``train`` stage entrypoint."""
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
        train_loader = DataLoader(
            train_dataset,
            batch_size=cfg.train.batch_size,
            shuffle=True,
            num_workers=cfg.train.num_workers,
        )
        build_trainer(cfg).fit(train_loader)

    _run()


if __name__ == "__main__":
    main()
