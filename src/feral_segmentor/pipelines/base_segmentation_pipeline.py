"""Base segmentation training pipeline (Hydra + PyTorch Lightning entrypoint)."""

from __future__ import annotations

from typing import Any

import hydra
import lightning as L
import torch
from omegaconf import DictConfig
from torch import nn
from torch.utils.data import DataLoader

from feral_segmentor.config.store import register_configs
from feral_segmentor.models.registry import build_model
from feral_segmentor.training.losses import segmentation_loss
from feral_segmentor.training.optim import build_optimizer, build_scheduler
from feral_segmentor.utils import get_logger

register_configs()

log = get_logger(__name__)


class SegmentationModule(L.LightningModule):
    """Lightning module wrapping any segmentation nn.Module with a configurable loss."""

    def __init__(self, model: nn.Module, cfg: DictConfig) -> None:
        super().__init__()
        self.model = model
        self.cfg = cfg

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Delegate to the wrapped model."""
        return self.model(x)

    def training_step(self, batch: Any, batch_idx: int) -> torch.Tensor:
        """Compute loss for one training batch and log it."""
        inputs, targets = batch
        logits = self(inputs)
        loss = segmentation_loss(logits, targets, self.cfg.train)
        self.log("train_loss", loss, on_step=True, on_epoch=True, prog_bar=True)
        return loss

    def validation_step(self, batch: Any, batch_idx: int) -> torch.Tensor:
        """Compute loss for one validation batch and log it."""
        inputs, targets = batch
        logits = self(inputs)
        loss = segmentation_loss(logits, targets, self.cfg.train)
        self.log("val_loss", loss, on_epoch=True, prog_bar=True)
        return loss

    def configure_optimizers(self):  # noqa: ANN201 — matches Lightning's union return type
        """Build optimizer and optional scheduler from cfg.train."""
        optimizer = build_optimizer(self.model.parameters(), self.cfg.train)
        scheduler = build_scheduler(optimizer, self.cfg.train)
        if scheduler is None:
            return {"optimizer": optimizer}
        return {
            "optimizer": optimizer,
            "lr_scheduler": {"scheduler": scheduler, "monitor": "val_loss"},
        }


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    """Train a segmentation model per the Hydra config."""
    register_configs()

    import feral_segmentor.models  # noqa: F401 — triggers architecture registration

    model = build_model(cfg.model)
    module = SegmentationModule(model=model, cfg=cfg)

    try:
        from lightning.pytorch.loggers import MLFlowLogger

        mlf_logger = MLFlowLogger(
            experiment_name=cfg.tracking.experiment_name,
            tracking_uri=cfg.tracking.tracking_uri,
        )
        loggers = [mlf_logger]
    except Exception:
        log.warning("MLflow logger unavailable; training without experiment tracking")
        loggers = []

    trainer = L.Trainer(
        max_epochs=int(cfg.train.epochs),
        logger=loggers or True,
        enable_progress_bar=True,
    )

    from feral_segmentor.data.dataset import SegmentationDataset

    dataset = SegmentationDataset(cfg.data.root)
    loader = DataLoader(
        dataset,
        batch_size=int(cfg.train.batch_size),
        shuffle=True,
        num_workers=int(cfg.train.num_workers),
    )
    trainer.fit(module, train_dataloaders=loader)


if __name__ == "__main__":
    main()
