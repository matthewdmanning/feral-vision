"""Source adapter base class.

Each model source (local file, cloud storage, online hub) has a concrete subclass
in this package. The training loop and registry workflow use the concrete class directly.

### Model Loading (training loop)
- fetch(cfg) -> nn.Module

### Model Registering
- inspect(cfg, *, fetch_if_needed=False) -> ModelProperties
"""

from __future__ import annotations

from omegaconf import DictConfig
from torch import nn

from feral_segmentor.models.ModelProperties import ModelProperties


class SourceAdapter:
    def fetch(self, cfg: DictConfig) -> nn.Module:
        raise NotImplementedError

    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> tuple[ModelProperties, dict]:
        """Return (ModelProperties, extra_metadata).

        extra_metadata holds anything the source exposes beyond the standard
        ModelProperties fields (class names, variant info, nc, etc.).
        """
        raise NotImplementedError


def _inspect_loaded(model: nn.Module) -> tuple[ModelProperties, dict]:
    for _, mod in reversed(list(model.named_modules())):
        if isinstance(mod, nn.Linear):
            return ModelProperties(), {}
        if isinstance(mod, nn.Conv2d):
            return ModelProperties(), {}
    return ModelProperties(), {}
