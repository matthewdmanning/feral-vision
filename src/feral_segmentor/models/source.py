"""Source adapter registry.

Each adapter normalises a different external system to the ModelSource protocol.
Dispatch is by cfg.architecture.source.
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar

from omegaconf import DictConfig
from torch import nn

from feral_segmentor.models.properties import ModelProperties

_SOURCES: dict[str, Any] = {}
_S = TypeVar("_S")


class ModelSource(Protocol):
    def fetch(self, cfg: DictConfig) -> None: ...
    def instantiate(self, cfg: DictConfig) -> nn.Module: ...
    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> ModelProperties: ...


def register_source(name: str) -> Callable[[_S], _S]:
    def decorator(cls: _S) -> _S:
        _SOURCES[name] = cls
        return cls

    return decorator


def get_source(name: str) -> ModelSource:
    try:
        return _SOURCES[name]()
    except KeyError:
        raise KeyError(
            f"unknown source {name!r}; registered: {sorted(_SOURCES)}"
        ) from None
