"""Structured-config dataclasses.

These are registered in :mod:`feral_vision.config.store` so that each YAML in
``conf/`` merges *onto* a typed node (Hydra's schema-as-defaults pattern). The
composed object stays a struct-mode ``DictConfig`` — fully mergeable and
CLI-overridable — while gaining type checking and rejecting unknown keys.

Required-at-runtime fields use ``omegaconf.MISSING``; everything else defaults to
a constant from :mod:`feral_vision.constants` (no magic numbers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from omegaconf import MISSING


# --- Data -------------------------------------------------------------------
@dataclass
class DataConfig:
    source: str = "local"
    root: str = "data"
    image_size: int = 256
    val_split: float = 0.2
    # Per-class morphological similarity to the target species (cat=1.0 anchor).
    # Length must match num_classes in the dataset. Empty list = uniform weights.
    class_similarity: list[float] = field(default_factory=list)


# --- Model --------------------------------------------------------------
@dataclass
class SourceConfig:
    """Where a model architecture or weights come from. Resolved by source adapter."""

    source: str = MISSING  # discriminator: hf_hub | torch_hub | ultralytics | ...
    id: str = MISSING  # hub repo ID, model name, dotted class path, or URL
    location: Optional[str] = None  # local path; None = hub loads directly into memory


@dataclass
class WeightsConfig:
    """Weight files to fetch and load. Independent of architecture source."""

    source: str = MISSING
    id: list[str] = field(default_factory=list)  # filenames, hub asset names, etc.
    location: Optional[str] = None  # local path; None = hub loads directly into memory


@dataclass
class ModelConfig:
    """Single source of truth for a model. architecture is required; weights is optional."""

    model_outputs: list[str] = field(default_factory=list)
    architecture: SourceConfig = MISSING
    weights: Optional[WeightsConfig] = None


# --- Training sub-configs ---------------------------------------------------
@dataclass
class OptimConfig:
    """Base contract for optimizer configs. Subclass for each concrete variant."""

    _target_: str = MISSING
    _partial_: bool = True


@dataclass
class LossFnConfig:
    """Base contract for loss function configs. Subclass for each concrete variant."""

    _target_: str = MISSING


@dataclass
class SchedulerConfig:
    """Base contract for scheduler configs. Subclass for each concrete variant."""

    _target_: str = MISSING
    _partial_: bool = True


# --- Optim variants ---------------------------------------------------------
@dataclass
class AdamWConfig(OptimConfig):
    _target_: str = "torch.optim.AdamW"
    lr: float = 1e-3
    betas: list[float] = field(default_factory=lambda: [0.9, 0.999])
    eps: float = 1e-8
    weight_decay: float = 1e-2
    amsgrad: bool = False


@dataclass
class AdamConfig(OptimConfig):
    _target_: str = "torch.optim.Adam"
    lr: float = 1e-3
    betas: list[float] = field(default_factory=lambda: [0.9, 0.999])
    eps: float = 1e-8
    weight_decay: float = 0.0
    amsgrad: bool = False


@dataclass
class SGDConfig(OptimConfig):
    _target_: str = "torch.optim.SGD"
    lr: float = 1e-2
    momentum: float = 0.9
    dampening: float = 0.0
    weight_decay: float = 0.0
    nesterov: bool = False


@dataclass
class RMSpropConfig(OptimConfig):
    _target_: str = "torch.optim.RMSprop"
    lr: float = 1e-2
    alpha: float = 0.99
    eps: float = 1e-8
    weight_decay: float = 0.0
    momentum: float = 0.0
    centered: bool = False


@dataclass
class RAdamConfig(OptimConfig):
    _target_: str = "torch.optim.RAdam"
    lr: float = 1e-3
    betas: list[float] = field(default_factory=lambda: [0.9, 0.999])
    eps: float = 1e-8
    weight_decay: float = 0.0


# --- Scheduler variants -----------------------------------------------------
@dataclass
class CosineAnnealingConfig(SchedulerConfig):
    _target_: str = "torch.optim.lr_scheduler.CosineAnnealingLR"
    T_max: int = 50
    eta_min: float = 0.0
    last_epoch: int = -1


@dataclass
class LinearLRConfig(SchedulerConfig):
    _target_: str = "torch.optim.lr_scheduler.LinearLR"
    start_factor: float = 0.3333333333333333
    end_factor: float = 1.0
    total_iters: int = 5
    last_epoch: int = -1


@dataclass
class StepLRConfig(SchedulerConfig):
    _target_: str = "torch.optim.lr_scheduler.StepLR"
    step_size: int = 10
    gamma: float = 0.1
    last_epoch: int = -1


@dataclass
class ReduceLROnPlateauConfig(SchedulerConfig):
    _target_: str = "torch.optim.lr_scheduler.ReduceLROnPlateau"
    mode: str = "min"
    factor: float = 0.1
    patience: int = 10
    threshold: float = 1e-4
    threshold_mode: str = "rel"
    cooldown: int = 0
    min_lr: float = 0.0
    eps: float = 1e-8


@dataclass
class CosineWarmRestartsConfig(SchedulerConfig):
    _target_: str = "torch.optim.lr_scheduler.CosineAnnealingWarmRestarts"
    T_0: int = 10
    T_mult: int = 1
    eta_min: float = 0.0
    last_epoch: int = -1


# --- Loss variants ----------------------------------------------------------
@dataclass
class CrossEntropyConfig(LossFnConfig):
    _target_: str = "torch.nn.CrossEntropyLoss"
    reduction: str = "mean"
    label_smoothing: float = 0.0
    ignore_index: int = -100


@dataclass
class BCEWithLogitsConfig(LossFnConfig):
    _target_: str = "torch.nn.BCEWithLogitsLoss"
    reduction: str = "mean"


@dataclass
class MSELossConfig(LossFnConfig):
    _target_: str = "torch.nn.MSELoss"
    reduction: str = "mean"


@dataclass
class L1LossConfig(LossFnConfig):
    _target_: str = "torch.nn.L1Loss"
    reduction: str = "mean"


@dataclass
class NLLLossConfig(LossFnConfig):
    _target_: str = "torch.nn.NLLLoss"
    reduction: str = "mean"
    ignore_index: int = -100


# --- Training ---------------------------------------------------------------
@dataclass
class TrainConfig:
    epochs: int = 50
    batch_size: int = 32
    num_workers: int = 0
    device: str = "cuda"
    optim: OptimConfig = MISSING
    loss_fn: LossFnConfig = MISSING
    scheduler: SchedulerConfig = MISSING


# --- Inference --------------------------------------------------------------
@dataclass
class InferenceConfig:
    threshold: float = 0.5
    device: str = "cpu"
    tta: bool = False
    min_box_area: int = 1


# --- Experiment tracking ----------------------------------------------------
@dataclass
class TrackingConfig:
    tracking_uri: str = MISSING
    experiment_name: str = MISSING


# --- Augmentation -----------------------------------------------------------
@dataclass
class AugmentationConfig:
    name: str = MISSING
    # Ordered list of registered augmentation op names; the chain builder maps
    # each name to a concrete Augmentation (params sourced from constants).
    ops: list[str] = field(default_factory=list)


# --- Top-level (type-hint convenience; group schemas are what get registered) ---
@dataclass
class Config:
    data: DataConfig = MISSING
    model: ModelConfig = MISSING
    train: TrainConfig = MISSING
    inference: InferenceConfig = MISSING
    tracking: TrackingConfig = MISSING
    augmentation: AugmentationConfig = MISSING
