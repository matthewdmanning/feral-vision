"""Source adapter base class.

Each model source (local file, cloud storage, online hub) has a concrete subclass
in this package. The training loop and registry workflow use the concrete class directly.

### Model Loading (training loop)
- ``fetch(cfg) -> nn.Module``

### Model Registering
- ``inspect(cfg) -> (ModelProperties, metadata)``
"""

from __future__ import annotations

from collections.abc import Iterable
from omegaconf import DictConfig
from torch import nn

from sightkit_learn.models.ModelProperties import ModelProperties


class SourceAdapter:
    discovery_filters = frozenset({"model_id", "architecture_location"})

    def list_models(
        self,
        *,
        query: str | None = None,
        repository: str | None = None,
        pipeline_tag: str | None = None,
    ) -> Iterable[dict]:
        """Use this function to discover provider model identifiers and inspection locations.

        Returns
        -------
        Iterable[dict]
            Candidates containing model_id and architecture_location. Discovery
            does not choose starting weights or save registry entries.
        """
        raise NotImplementedError("this adapter does not implement model discovery")

    def fetch(self, cfg: DictConfig) -> nn.Module:
        raise NotImplementedError

    def inspect(self, cfg: DictConfig) -> tuple[ModelProperties, dict]:
        """Return (ModelProperties, extra_metadata).

        extra_metadata holds provider facts useful for training setup, such as
        class information, available weights and constructor documentation.
        Inspection must not construct models, execute repository code or load weights.
        """
        raise NotImplementedError
