"""Optimizer and LR-scheduler builders.

Thin wrappers over ``hydra.utils.instantiate`` so callers don't need to import
Hydra directly.  Each :class:`OptimConfig` / :class:`SchedulerConfig` carries
``_target_`` and ``_partial_: true``, so instantiate returns a factory that
still needs its first positional argument (``params`` / ``optimizer``).
"""

from __future__ import annotations

from collections.abc import Iterable

import torch
from torch import nn


def build_optimizer(
    params: Iterable[nn.Parameter],
    cfg_optim: object,
) -> torch.optim.Optimizer:
    """Instantiate and return an optimizer bound to ``params``.

    Parameters
    ----------
    params : Iterable[nn.Parameter]
        Parameter iterable (e.g. ``model.parameters()``).
    cfg_optim : object
        An ``OptimConfig`` DictConfig with ``_target_`` and
        ``_partial_: true`` set.

    Returns
    -------
    torch.optim.Optimizer
        Configured optimizer instance.
    """
    from hydra.utils import instantiate

    return instantiate(cfg_optim)(params)


def build_scheduler(
    optimizer: torch.optim.Optimizer,
    cfg_scheduler: object | None,
) -> torch.optim.lr_scheduler.LRScheduler | None:
    """Instantiate and return an LR scheduler, or ``None``.

    Parameters
    ----------
    optimizer : torch.optim.Optimizer
        The optimizer whose learning rate is scheduled.
    cfg_scheduler : object or None
        A ``SchedulerConfig`` DictConfig with ``_target_`` and
        ``_partial_: true`` set, or ``None`` to disable scheduling.

    Returns
    -------
    torch.optim.lr_scheduler.LRScheduler or None
        Configured scheduler instance, or ``None`` when disabled.
    """
    if cfg_scheduler is None:
        return None

    from hydra.utils import instantiate

    return instantiate(cfg_scheduler)(optimizer)


def build_loss_fn(cfg_loss_fn: object) -> nn.Module:
    """Instantiate and return a loss function module.

    Parameters
    ----------
    cfg_loss_fn : object
        A ``LossFnConfig`` DictConfig with ``_target_`` set (no
        ``_partial_``; loss functions are instantiated directly).

    Returns
    -------
    torch.nn.Module
        Configured loss instance (e.g. ``CrossEntropyLoss``).
    """
    from hydra.utils import instantiate

    return instantiate(cfg_loss_fn)
