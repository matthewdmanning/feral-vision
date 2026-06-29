"""Structured-config dataclasses.

These are registered in :mod:`feral_segmentor.config.store` so that each YAML in
``conf/`` merges *onto* a typed node (Hydra's schema-as-defaults pattern). The
composed object stays a struct-mode ``DictConfig`` — fully mergeable and
CLI-overridable — while gaining type checking and rejecting unknown keys.

Required-at-runtime fields use ``omegaconf.MISSING``; everything else defaults to
a constant from :mod:`feral_segmentor.constants` (no magic numbers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from omegaconf import MISSING

from feral_segmentor import constants as C


# --- Data -------------------------------------------------------------------
@dataclass
class DataConfig:
    source: str = C.DEFAULT_DATA_SOURCE
    root: str = "data"
    image_size: int = C.DEFAULT_IMAGE_SIZE
    val_split: float = C.DEFAULT_VAL_SPLIT
    # Per-class morphological similarity to the target species (cat=1.0 anchor).
    # Length must match num_classes in the dataset. Empty list = uniform weights.
    class_similarity: list[float] = field(default_factory=list)


# --- Model ------------------------------------------------------------------
@dataclass
class SourceConfig:
    """Where a model architecture or weights come from. Resolved by source adapter."""

    source: str = MISSING  # discriminator: hf_hub | yolo_hub | local | url | ...
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


# --- Training ---------------------------------------------------------------
@dataclass
class TrainConfig:
    epochs: int = C.DEFAULT_EPOCHS
    lr: float = C.DEFAULT_LR
    batch_size: int = C.DEFAULT_BATCH_SIZE
    optimizer: str = C.DEFAULT_OPTIMIZER
    scheduler: str = C.DEFAULT_SCHEDULER
    weight_decay: float = C.DEFAULT_WEIGHT_DECAY
    momentum: float = C.DEFAULT_MOMENTUM
    num_workers: int = C.DEFAULT_NUM_WORKERS
    scheduler_step_size: int = C.DEFAULT_SCHEDULER_STEP_SIZE
    scheduler_gamma: float = C.DEFAULT_SCHEDULER_GAMMA
    dice_weight: float = C.DEFAULT_DICE_WEIGHT
    bce_weight: float = C.DEFAULT_BCE_WEIGHT
    distill_weight: float = C.DEFAULT_DISTILL_WEIGHT
    distill_temperature: float = C.DEFAULT_DISTILL_TEMPERATURE
    # Similarity-weighted training. Set use_similarity=true to activate.
    # similarity_loss / similarity_sampler are dotted import paths to callables
    # resolved at runtime via importlib; "none" disables each respectively.
    use_similarity: bool = False
    similarity_loss: str = "none"
    similarity_sampler: str = "none"


# --- Inference --------------------------------------------------------------
@dataclass
class InferenceConfig:
    threshold: float = C.DEFAULT_MASK_THRESHOLD
    device: str = C.DEFAULT_DEVICE
    tta: bool = C.DEFAULT_TTA
    min_box_area: int = C.DEFAULT_MIN_BOX_AREA


# --- Experiment tracking ----------------------------------------------------
@dataclass
class TrackingConfig:
    tracking_uri: str = MISSING
    experiment_name: str = MISSING


# --- Augmentation -----------------------------------------------------------
@dataclass
class AugmentationConfig:
    name: str = MISSING
    # Each op is a dict with a required 'name' key (short Albumentations class
    # name or fully-qualified path) plus any kwargs the transform accepts.
    # Short names are resolved via getattr(albumentations, name); fully qualified
    # names (containing a dot) are resolved via importlib. Per-op kwargs flow
    # directly to the transform constructor, so any Albumentations transform is
    # supported without a registry.
    ops: list[Any] = field(default_factory=list)


# --- Top-level (type-hint convenience; group schemas are what get registered) ---
@dataclass
class Config:
    data: DataConfig = MISSING
    model: ModelConfig = MISSING
    train: TrainConfig = MISSING
    inference: InferenceConfig = MISSING
    tracking: TrackingConfig = MISSING
    augmentation: AugmentationConfig = MISSING
