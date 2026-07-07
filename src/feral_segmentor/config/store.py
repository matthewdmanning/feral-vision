"""Register structured-config schemas with Hydra's ConfigStore.

We register one schema per config-group *variant* (e.g. ``model/base_hub``).
Each YAML under ``conf/<group>/`` opts in with ``defaults: [base_<variant>]`` so
it merges onto the typed node. We intentionally do **not** register a top-level
``Config`` node: typing the nested group fields as their base class would make a
heterogeneous subtype (e.g. ``HubModelConfig`` with extra ``repo_id``) fail the
struct merge into ``ModelConfig``. Per-group registration gives the same
validation without that pitfall, and the composed object stays a mergeable
``DictConfig``.

``register_configs`` is idempotent so it can be called from every Hydra
entrypoint without double-registration errors.
"""

from __future__ import annotations

from hydra.core.config_store import ConfigStore

from feral_segmentor.config.schema import (
    AugmentationConfig,
    ConfigModelConfig,
    DataConfig,
    HubModelConfig,
    InferenceConfig,
    ScriptModelConfig,
    TeacherModelConfig,
    # Loss base + variants
    LossFnConfig,
    CrossEntropyConfig,
    BCEWithLogitsConfig,
    MSELossConfig,
    L1LossConfig,
    NLLLossConfig,
    # Optim base + variants
    OptimConfig,
    AdamWConfig,
    AdamConfig,
    SGDConfig,
    RMSpropConfig,
    RAdamConfig,
    # Scheduler base + variants
    SchedulerConfig,
    CosineAnnealingConfig,
    LinearLRConfig,
    StepLRConfig,
    ReduceLROnPlateauConfig,
    CosineWarmRestartsConfig,
    TrackingConfig,
    TrainConfig,
)

# (group, schema-name, node) — schema-name is what YAML references in its
# `defaults:` list, resolved relative to the group.
_SCHEMAS: tuple[tuple[str, str, type], ...] = (
    ("data", "base_data", DataConfig),
    ("model", "base_hub", HubModelConfig),
    ("model", "base_script", ScriptModelConfig),
    ("model", "base_config_source", ConfigModelConfig),
    ("model", "base_teacher", TeacherModelConfig),
    ("train", "base_train", TrainConfig),
    # Base schemas — type contracts for TrainConfig fields
    ("train/optim", "base_optim", OptimConfig),
    ("train/loss_fn", "base_loss_fn", LossFnConfig),
    ("train/scheduler", "base_scheduler", SchedulerConfig),
    # Optim variants
    ("train/optim", "adamw", AdamWConfig),
    ("train/optim", "adam", AdamConfig),
    ("train/optim", "sgd", SGDConfig),
    ("train/optim", "rmsprop", RMSpropConfig),
    ("train/optim", "radam", RAdamConfig),
    # Scheduler variants
    ("train/scheduler", "cosine", CosineAnnealingConfig),
    ("train/scheduler", "linear", LinearLRConfig),
    ("train/scheduler", "step", StepLRConfig),
    ("train/scheduler", "plateau", ReduceLROnPlateauConfig),
    ("train/scheduler", "warmrestarts", CosineWarmRestartsConfig),
    # Loss variants
    ("train/loss_fn", "cross_entropy", CrossEntropyConfig),
    ("train/loss_fn", "bce_with_logits", BCEWithLogitsConfig),
    ("train/loss_fn", "mse", MSELossConfig),
    ("train/loss_fn", "l1", L1LossConfig),
    ("train/loss_fn", "nll", NLLLossConfig),
    # Other configs
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
