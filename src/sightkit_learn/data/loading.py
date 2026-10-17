"""Shared Hydra construction for prepared PyTorch DataLoaders."""

from collections.abc import Callable

from hydra.utils import instantiate
from omegaconf import DictConfig
from torch.utils.data import DataLoader


def instantiate_dataloader(
    specification: DictConfig, *, collate_fn: Callable | None = None
) -> DataLoader:
    """Instantiate a prepared loader, preserving its explicitly selected collator.

    Parameters
    ----------
    specification : DictConfig
        Hydra target containing the dataset, transforms, and loader settings.
    collate_fn : callable, optional
        Collator used only when the loader specification does not supply one.

    Returns
    -------
    DataLoader
        Loader with the dataset's native sample contract.
    """
    if "collate_fn" in specification:
        return instantiate(specification)
    return instantiate(specification, collate_fn=collate_fn)
