"""Optimizer and LR-scheduler builders.

Registries map config names directly to PyTorch classes. Per-variant config
dataclasses declare the hyperparameters each class expects; ``build_optimizer``
and ``build_scheduler`` pull matching fields from the Hydra TrainConfig.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

import torch
from torch import nn

from feral_segmentor import constants as C


# --- Per-variant config dataclasses -----------------------------------------


@dataclass
class AdamConfig:
    lr: float = C.DEFAULT_LR
    weight_decay: float = C.DEFAULT_WEIGHT_DECAY


@dataclass
class SGDConfig:
    lr: float = C.DEFAULT_LR
    weight_decay: float = C.DEFAULT_WEIGHT_DECAY
    momentum: float = C.DEFAULT_MOMENTUM


@dataclass
class StepLRConfig:
    step_size: int = C.DEFAULT_SCHEDULER_STEP_SIZE
    gamma: float = C.DEFAULT_SCHEDULER_GAMMA


@dataclass
class CosineAnnealingLRConfig:
    T_max: int = C.DEFAULT_EPOCHS


# --- Registries: name → PyTorch class ---------------------------------------

_OPTIMIZERS: dict[str, type[torch.optim.Optimizer]] = {
    "adam": torch.optim.Adam,
    "sgd": torch.optim.SGD,
}

_OPTIMIZER_CONFIGS: dict[str, type] = {
    "adam": AdamConfig,
    "sgd": SGDConfig,
}

_SCHEDULERS: dict[str, type[torch.optim.lr_scheduler.LRScheduler]] = {
    "step": torch.optim.lr_scheduler.StepLR,
    "cosine": torch.optim.lr_scheduler.CosineAnnealingLR,
}

_SCHEDULER_CONFIGS: dict[str, type] = {
    "step": StepLRConfig,
    "cosine": CosineAnnealingLRConfig,
}

# cfg field name → constructor kwarg name for cases that differ
_SCHEDULER_FIELD_MAP: dict[str, dict[str, str]] = {
    "cosine": {"T_max": "epochs"},  # CosineAnnealingLR.T_max ← cfg.epochs
}


# --- Public builders --------------------------------------------------------


def build_optimizer(params: Iterable[nn.Parameter], cfg: Any) -> torch.optim.Optimizer:
    """Construct the optimizer named by ``cfg.optimizer``."""
    name = str(cfg.optimizer)
    try:
        cls = _OPTIMIZERS[name]
        cfg_cls = _OPTIMIZER_CONFIGS[name]
    except KeyError:
        raise ValueError(
            f"unknown optimizer {name!r}; choose from {sorted(_OPTIMIZERS)}"
        ) from None
    kwargs: dict[str, Any] = {
        f.name: v
        for f in dataclasses.fields(cfg_cls)
        if (v := getattr(cfg, f.name, f.default)) is not dataclasses.MISSING
    }
    return cls(params, **kwargs)


def build_scheduler(
    optimizer: torch.optim.Optimizer, cfg: Any
) -> torch.optim.lr_scheduler.LRScheduler | None:
    """Construct the LR scheduler named by ``cfg.scheduler``.

    Returns ``None`` for ``"none"`` so callers can skip ``scheduler.step()``
    when the result is falsy.
    """
    name = str(cfg.scheduler)
    if name == "none":
        return None
    try:
        cls = _SCHEDULERS[name]
        cfg_cls = _SCHEDULER_CONFIGS[name]
    except KeyError:
        raise ValueError(
            f"unknown scheduler {name!r}; choose from {sorted(_SCHEDULERS)}"
        ) from None
    field_map = _SCHEDULER_FIELD_MAP.get(name, {})
    kwargs: dict[str, Any] = {
        f.name: v
        for f in dataclasses.fields(cfg_cls)
        if (v := getattr(cfg, field_map.get(f.name, f.name), f.default))
        is not dataclasses.MISSING
    }
    return cls(optimizer, **kwargs)
