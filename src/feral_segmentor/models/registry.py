"""Architecture registry. Each nn.Module subclass self-registers via @register."""

from __future__ import annotations

from typing import Any, Callable, TypeVar

from omegaconf import DictConfig
from torch import nn

from feral_segmentor.tasks import CVTask

DEFAULT_ARCH: str = "net"

# Values are Any so registered classes may define from_config without mypy
# needing a Protocol with a classmethod (which is unsound in Python's type system).
_ARCHITECTURES: dict[str, Any] = {}

_M = TypeVar("_M")


def register(name: str) -> Callable[[_M], _M]:
    """Decorator that registers an nn.Module subclass under ``name``."""

    def decorator(cls: _M) -> _M:
        _ARCHITECTURES[name] = cls
        return cls

    return decorator


def build_model(cfg: DictConfig) -> nn.Module:
    """Build from cfg.arch (falls back to DEFAULT_ARCH) via cls.from_config(cfg)."""
    arch = str(cfg.get("arch", DEFAULT_ARCH))
    try:
        cls = _ARCHITECTURES[arch]
    except KeyError:
        raise KeyError(
            f"unknown architecture {arch!r}; registered: {sorted(_ARCHITECTURES)}"
        ) from None
    return cls.from_config(cfg)


def get_model(name: str = DEFAULT_ARCH) -> nn.Module:
    """Return a default-constructed instance of the named architecture."""
    try:
        cls = _ARCHITECTURES[name]
    except KeyError:
        raise KeyError(
            f"unknown architecture {name!r}; registered: {sorted(_ARCHITECTURES)}"
        ) from None
    return cls()


def get_model_tasks(model_cfg: DictConfig) -> list[CVTask]:
    """Return the CVTask list declared in a composed model config."""
    return [CVTask(t) for t in model_cfg.model_tasks]
