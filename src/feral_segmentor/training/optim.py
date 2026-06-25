"""Optimizer and LR-scheduler builders (registry/adapter pattern).

Each public builder dispatches on a name read from the :class:`TrainConfig`
node against a module-level registry mapping ``name -> builder fn``. Adding a
new optimizer or scheduler is a single registry entry; logic stays branch-free.
Hyperparameters are read from the config (which itself defaults to constants), so
no magic numbers appear here.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

import torch
from torch import nn

# A ``TrainConfig`` is accessed both as a dataclass and as a struct-mode
# ``DictConfig`` after OmegaConf composition; attribute access works for both.

OptimizerBuilder = Callable[[Iterable[nn.Parameter], object], torch.optim.Optimizer]
SchedulerBuilder = Callable[
    [torch.optim.Optimizer, object],
    "torch.optim.lr_scheduler.LRScheduler | None",
]


def _build_adam(
    params: Iterable[nn.Parameter], cfg: object
) -> torch.optim.Optimizer:
    return torch.optim.Adam(
        params, lr=cfg.lr, weight_decay=cfg.weight_decay
    )


def _build_sgd(
    params: Iterable[nn.Parameter], cfg: object
) -> torch.optim.Optimizer:
    return torch.optim.SGD(
        params,
        lr=cfg.lr,
        weight_decay=cfg.weight_decay,
        momentum=cfg.momentum,
    )


_OPTIMIZERS: dict[str, OptimizerBuilder] = {
    "adam": _build_adam,
    "sgd": _build_sgd,
}


def build_optimizer(
    params: Iterable[nn.Parameter], cfg: object
) -> torch.optim.Optimizer:
    """Construct the optimizer named by ``cfg.optimizer``.

    Args:
        params: Parameters to optimize (e.g. ``model.parameters()``).
        cfg: A ``TrainConfig`` (dataclass or struct-mode ``DictConfig``)
            providing ``optimizer``, ``lr``, ``weight_decay`` and ``momentum``.

    Raises:
        ValueError: If ``cfg.optimizer`` is not a registered name.
    """
    name = cfg.optimizer
    try:
        builder = _OPTIMIZERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown optimizer {name!r}; expected one of "
            f"{sorted(_OPTIMIZERS)}."
        ) from None
    return builder(params, cfg)


def _build_no_scheduler(
    optimizer: torch.optim.Optimizer, cfg: object
) -> None:
    return None


def _build_step_scheduler(
    optimizer: torch.optim.Optimizer, cfg: object
) -> torch.optim.lr_scheduler.LRScheduler:
    return torch.optim.lr_scheduler.StepLR(
        optimizer,
        step_size=cfg.scheduler_step_size,
        gamma=cfg.scheduler_gamma,
    )


def _build_cosine_scheduler(
    optimizer: torch.optim.Optimizer, cfg: object
) -> torch.optim.lr_scheduler.LRScheduler:
    return torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=cfg.epochs
    )


_SCHEDULERS: dict[str, SchedulerBuilder] = {
    "none": _build_no_scheduler,
    "step": _build_step_scheduler,
    "cosine": _build_cosine_scheduler,
}


def build_scheduler(
    optimizer: torch.optim.Optimizer, cfg: object
) -> torch.optim.lr_scheduler.LRScheduler | None:
    """Construct the LR scheduler named by ``cfg.scheduler``.

    Returns ``None`` for the ``"none"`` policy so callers can simply skip
    ``scheduler.step()`` when the result is falsy.

    Args:
        optimizer: The optimizer whose learning rate is scheduled.
        cfg: A ``TrainConfig`` providing ``scheduler`` plus the relevant
            schedule hyperparameters (``scheduler_step_size``,
            ``scheduler_gamma``, ``epochs``).

    Raises:
        ValueError: If ``cfg.scheduler`` is not a registered name.
    """
    name = cfg.scheduler
    try:
        builder = _SCHEDULERS[name]
    except KeyError:
        raise ValueError(
            f"Unknown scheduler {name!r}; expected one of "
            f"{sorted(_SCHEDULERS)}."
        ) from None
    return builder(optimizer, cfg)
