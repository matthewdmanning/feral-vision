"""Register structured-config schemas with Hydra's ConfigStore.

We register one schema per config-group *variant* (e.g. ``model/base_hub``).
Each YAML under ``conf/<group>/`` opts in with ``defaults: [base_<variant>]`` so
it merges onto the typed node. ``register_configs`` is idempotent so it can be
called from every Hydra entrypoint without double-registration errors.
"""

from __future__ import annotations

from hydra.core.config_store import ConfigStore

from feral_segmentor.config.schema import (
    AugmentationConfig,
    DataConfig,
    HubModelConfig,
    InferenceConfig,
    TrackingConfig,
    TrainConfig,
)

# (group, schema-name, node) — schema-name is what YAML references in its
# `defaults:` list, resolved relative to the group.
_SCHEMAS: tuple[tuple[str, str, type], ...] = (
    ("data", "base_data", DataConfig),
    ("model", "base_hub", HubModelConfig),
    ("train", "base_train", TrainConfig),
    ("inference", "base_inference", InferenceConfig),
    ("tracking", "base_tracking", TrackingConfig),
    ("augmentation", "base_augmentation", AugmentationConfig),
)

_registered = False


def register_configs() -> None:
    """Register all group schemas with the global ConfigStore (idempotent)."""
    global _registered
    if _registered:
        return
    cs = ConfigStore.instance()
    for group, name, node in _SCHEMAS:
        cs.store(group=group, name=name, node=node)
    _registered = True
