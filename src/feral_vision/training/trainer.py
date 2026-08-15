"""Canonical Hydra training entrypoint."""

from typing import Any

import hydra
from hydra.utils import to_absolute_path
from torch.utils.data import DataLoader

from feral_vision.config.store import register_configs
from feral_vision.data.dataset import AnnotationDataset
from feral_vision.io_utils import DatasetSource
from feral_vision.models.register_model import model_builder
from feral_vision.training.optim import build_loss_fn, build_optimizer, build_scheduler
from feral_vision.training.task_adapters import DetectionTaskAdapter
from feral_vision.training.Trainer import Trainer

register_configs()


@hydra.main(version_base=None, config_path="../../../conf", config_name="runs/baseline")
def main(cfg: Any) -> None:
    """Use this function to execute one Hydra-configured training run."""
    model = model_builder(cfg.model)
    optimizer = build_optimizer(model.parameters(), cfg.train.optim)
    scheduler = build_scheduler(optimizer, cfg.train.scheduler)
    task_adapter = (
        DetectionTaskAdapter(num_classes=int(cfg.train.num_classes))
        if getattr(cfg.train, "task", "generic") == "detection"
        else None
    )
    trainer = Trainer(
        model=model,
        optimizer=optimizer,
        scheduler=scheduler,
        loss_fn=build_loss_fn(cfg.train.loss_fn),
        cfg=cfg,
        task_adapter=task_adapter,
        device=cfg.train.device,
    )
    dataset = AnnotationDataset(DatasetSource(to_absolute_path(cfg.data.root)))
    trainer.fit(
        DataLoader(
            dataset,
            batch_size=cfg.train.batch_size,
            shuffle=True,
            num_workers=cfg.train.num_workers,
            collate_fn=task_adapter.collate if task_adapter else None,
        )
    )


if __name__ == "__main__":
    main()
