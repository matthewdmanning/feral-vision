"""Inference loading of prepared datasets through the shared data boundary."""

from hydra.utils import instantiate
from omegaconf import DictConfig
from torch.utils.data import DataLoader

from sightkit_learn.data.loading import instantiate_dataloader


def build_dataloader(cfg: DictConfig) -> DataLoader:
    """Build the Hydra-selected inference DataLoader without training defaults.

    Parameters
    ----------
    cfg : DictConfig
        Configuration containing inference DataLoader and optional collator targets.

    Returns
    -------
    DataLoader
        Prepared batches for predict_batches or labeled predict_dataset execution.
    """
    options = cfg.inference
    if options.dataloader is None:
        raise ValueError("Set inference.dataloader to the prepared DataLoader to use")
    return instantiate_dataloader(
        options.dataloader,
        collate_fn=instantiate(options.collate_fn, _convert_="all"),
    )
