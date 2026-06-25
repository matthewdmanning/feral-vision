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
from typing import Any, Callable, Iterable

import torch
from torch import nn

from feral_segmentor.utils import get_logger

logger = get_logger(__name__)

# --- Named module constants (no magic numbers) ------------------------------
# Default location for the best checkpoint; matches the DVC `train` stage out.
DEFAULT_BEST_MODEL_PATH: str = "models/registry/best.pt"
# Sentinel "no best yet" loss so the first finite epoch loss always wins.
INITIAL_BEST_LOSS: float = math.inf

LossFn = Callable[[Any, Any], torch.Tensor]


def _try_log_metric(name: str, value: float, step: int) -> None:
    """Log a metric to MLflow only when a run is active.

    Guarded so the trainer never requires a running tracking server: if mlflow
    is unavailable or no run is active, logging is silently skipped.
    """
    try:
        import mlflow

        if mlflow.active_run() is not None:
            mlflow.log_metric(name, value, step=step)
    except Exception:  # pragma: no cover - logging must never break training
        pass


class Trainer:
    """Minimal, dependency-injected supervised training loop."""

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
        self.device = torch.device(device) if device is not None else torch.device("cpu")
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

            running_loss += float(loss.detach().item())
            batch_count += 1

        if self.scheduler is not None:
            self.scheduler.step()

        return running_loss / batch_count if batch_count else INITIAL_BEST_LOSS

    @torch.no_grad()
    def _validate(self, dataloader: Iterable[Any]) -> float:
        self.model.eval()
        running_loss = 0.0
        batch_count = 0
        for inputs, targets in dataloader:
            inputs = self._move(inputs)
            targets = self._move(targets)
            outputs = self.model(inputs)
            loss = self.loss_fn(outputs, targets)
            running_loss += float(loss.detach().item())
            batch_count += 1
        return running_loss / batch_count if batch_count else INITIAL_BEST_LOSS

    def _save_best(self) -> None:
        self.best_model_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.model.state_dict(), self.best_model_path)

    def fit(
        self,
        dataloader: Iterable[Any],
        val_dataloader: Iterable[Any] | None = None,
    ) -> dict[str, Any]:
        """Run the training loop for ``cfg.train.epochs`` epochs.

        Returns a history dict with per-epoch train (and optional val) losses
        and the best loss observed. The best model state_dict is written to
        ``self.best_model_path`` whenever the tracked loss improves.
        """
        epochs = int(self.cfg.train.epochs)
        history: dict[str, Any] = {"train_loss": [], "val_loss": [], "best_loss": None}

        for epoch in range(epochs):
            train_loss = self._train_one_epoch(dataloader)
            history["train_loss"].append(train_loss)
            _try_log_metric("train_loss", train_loss, epoch)
            logger.info("epoch %d/%d train_loss=%.6f", epoch + 1, epochs, train_loss)

            # The loss used to pick the best checkpoint is val loss when given,
            # otherwise train loss.
            tracked_loss = train_loss
            if val_dataloader is not None:
                val_loss = self._validate(val_dataloader)
                history["val_loss"].append(val_loss)
                _try_log_metric("val_loss", val_loss, epoch)
                logger.info("epoch %d/%d val_loss=%.6f", epoch + 1, epochs, val_loss)
                tracked_loss = val_loss

            if tracked_loss < self.best_loss:
                self.best_loss = tracked_loss
                self._save_best()

        history["best_loss"] = self.best_loss
        return history


def build_trainer(cfg: Any) -> Trainer:
    """Wire a :class:`Trainer` with the real collaborators from other units.

    Imports are local so this module imports cleanly even while collaborators
    are skeletons; ``build_trainer`` is only called from the DVC entrypoint.
    """
    from feral_segmentor.models.registry import build_model
    from feral_segmentor.training.losses import segmentation_loss
    from feral_segmentor.training.optim import build_optimizer, build_scheduler

    model = build_model(cfg.model)
    optimizer = build_optimizer(model.parameters(), cfg.train)
    scheduler = build_scheduler(optimizer, cfg.train)

    def loss_fn(outputs: Any, targets: Any) -> torch.Tensor:
        return segmentation_loss(outputs, targets, cfg.train)

    return Trainer(
        model=model,
        optimizer=optimizer,
        loss_fn=loss_fn,
        cfg=cfg,
        scheduler=scheduler,
    )


def main() -> None:
    """DVC ``train`` stage entrypoint."""
    import hydra
    from torch.utils.data import DataLoader

    from feral_segmentor.config.store import register_configs

    register_configs()

    @hydra.main(version_base=None, config_path="../../conf", config_name="config")
    def _run(cfg: Any) -> None:
        from feral_segmentor.data.dataset import SegmentationDataset

        dataset = SegmentationDataset(cfg.data.root)
        loader = DataLoader(
            dataset,
            batch_size=int(cfg.train.batch_size),
            shuffle=True,
            num_workers=int(cfg.train.num_workers),
        )
        build_trainer(cfg).fit(loader)

    _run()


if __name__ == "__main__":
    main()
