"""Register structured-config schemas with Hydra's ConfigStore.

We register one schema per config-group *contract*. Each semantic YAML under
``conf/<group>/`` opts in with its group's ``*_schema`` entry so
it merges onto the typed node.

``register_configs`` is idempotent so it can be called from every Hydra
entrypoint without double-registration errors.
"""

from __future__ import annotations

from hydra.core.config_store import ConfigStore

from feral_vision.config.schema import (
    AugmentationConfig,
    DataConfig,
    InferenceConfig,
    ModelConfig,
    # Loss variants
    CrossEntropyConfig,
    BCEWithLogitsConfig,
    MSELossConfig,
    L1LossConfig,
    NLLLossConfig,
    # Optim variants
    AdamWConfig,
    AdamConfig,
    SGDConfig,
    RMSpropConfig,
    RAdamConfig,
    # Scheduler variants
    CosineAnnealingConfig,
    LinearLRConfig,
    StepLRConfig,
    ReduceLROnPlateauConfig,
    CosineWarmRestartsConfig,
    TrackingConfig,
    TrainConfig,
)

# (group, schema-name, node) — schema names are implementation contracts, not
# user-selectable configuration variants.
_SCHEMAS: tuple[tuple[str, str, type], ...] = (
    ("data", "data_schema", DataConfig),
    ("model", "model_schema", ModelConfig),
    ("train", "train_schema", TrainConfig),
    # Concrete sub-config contracts.
    ("train/optim", "adamw_schema", AdamWConfig),
    ("train/optim", "adam_schema", AdamConfig),
    ("train/optim", "sgd_schema", SGDConfig),
    ("train/optim", "rmsprop_schema", RMSpropConfig),
    ("train/optim", "radam_schema", RAdamConfig),
    # Scheduler variants
    ("train/scheduler", "cosine_schema", CosineAnnealingConfig),
    ("train/scheduler", "linear_schema", LinearLRConfig),
    ("train/scheduler", "step_schema", StepLRConfig),
    ("train/scheduler", "plateau_schema", ReduceLROnPlateauConfig),
    ("train/scheduler", "warmrestarts_schema", CosineWarmRestartsConfig),
    # Loss variants
    ("train/loss_fn", "cross_entropy_schema", CrossEntropyConfig),
    ("train/loss_fn", "bce_with_logits_schema", BCEWithLogitsConfig),
    ("train/loss_fn", "mse_schema", MSELossConfig),
    ("train/loss_fn", "l1_schema", L1LossConfig),
    ("train/loss_fn", "nll_schema", NLLLossConfig),
    # Other configs
    ("inference", "inference_schema", InferenceConfig),
    ("tracking", "tracking_schema", TrackingConfig),
    ("augmentation", "augmentation_schema", AugmentationConfig),
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
