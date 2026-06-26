"""Weight-source adapter registry.

Each source is an Adapter that normalises a different external system
(HuggingFace Hub, PyTorch Hub, etc.) to the common WeightSource Protocol.
``load_model`` dispatches by cfg.source.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar

from omegaconf import DictConfig
from torch import nn


class WeightSource(Protocol):
    """Protocol for weight-source adapters."""

    def load(self, cfg: DictConfig) -> nn.Module:
        """Load and return a fully initialised model from the config."""
        ...


# Values are Any so the TypeVar-based decorator can assign without a cast.
_SOURCES: dict[str, Any] = {}

_S = TypeVar("_S")


def register_source(name: str) -> Callable[[_S], _S]:
    """Decorator to register a weight-source adapter class under ``name``."""

    def decorator(cls: _S) -> _S:
        _SOURCES[name] = cls
        return cls

    return decorator


def load_model(cfg: DictConfig) -> nn.Module:
    """Load a model via the source named by cfg.source."""
    name = str(cfg.source)
    try:
        cls = _SOURCES[name]
    except KeyError:
        raise KeyError(
            f"unknown source {name!r}; registered: {sorted(_SOURCES)}"
        ) from None
    return cls().load(cfg)
