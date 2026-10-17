"""Torch Hub source adapter.

architecture.id  — torch.hub repo (e.g. 'ultralytics/ultralytics')
weights.id[0]    — model name passed to torch.hub.load (e.g. 'yolo11n-seg')
"""

from __future__ import annotations

from omegaconf import DictConfig
from torch import nn

from sightkit_learn.models.ModelProperties import ModelProperties
from sightkit_learn.models.sources.SourceAdapter import SourceAdapter, _inspect_loaded
from sightkit_learn.utils import get_logger

SOURCE_KEY = "torch_hub"
log = get_logger(__name__)


class TorchHubAdapter(SourceAdapter):
    """Load the configured Hub entrypoint with Hydra-selected native options."""

    def fetch(self, cfg: DictConfig) -> nn.Module:
        """Delegate configured model construction to the upstream Hub implementation."""
        import torch

        weights = getattr(cfg, "weights", None)
        model_name = weights.id[0] if weights and weights.id else "default"
        log.info("loading %s from torch.hub repo %s", model_name, cfg.architecture.id)
        from hydra.utils import instantiate

        options = {
            "verbose": False,
            "trust_repo": True,
            **instantiate(cfg.architecture.get("kwargs", {}), _convert_="all"),
        }
        return torch.hub.load(cfg.architecture.id, model_name, **options)

    def inspect(
        self, cfg: DictConfig, *, fetch_if_needed: bool = False
    ) -> tuple[ModelProperties, dict]:
        from sightkit_learn.models.register_model import load_model_registry

        try:
            return load_model_registry(cfg.architecture.id), {}
        except KeyError:
            pass

        if not fetch_if_needed:
            raise RuntimeError(
                "torch.hub provides no metadata API; pass fetch_if_needed=True to load and inspect locally"
            )

        return _inspect_loaded(self.fetch(cfg))
