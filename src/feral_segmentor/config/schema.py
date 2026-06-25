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

from omegaconf import MISSING

from feral_segmentor import constants as C


# --- Data -------------------------------------------------------------------
@dataclass
class DataConfig:
    source: str = C.DEFAULT_DATA_SOURCE
    root: str = "data"
    image_size: int = C.DEFAULT_IMAGE_SIZE
    val_split: float = C.DEFAULT_VAL_SPLIT


# --- Model: architecture (shared) + acquisition source (discriminated) ------
@dataclass
class ModelConfig:
    """Base/interface for the model group.

    Architecture fields are shared by every variant (a model has an
    architecture regardless of how its weights are obtained). ``source`` is the
    discriminator consumed by the acquisition factory.
    """

    name: str = MISSING
    source: str = MISSING
    in_channels: int = C.DEFAULT_IN_CHANNELS
    base_channels: int = C.DEFAULT_BASE_CHANNELS
    num_classes: int = C.DEFAULT_NUM_CLASSES


@dataclass
class HubModelConfig(ModelConfig):
    """Weights fetched from the Hugging Face Hub."""

    source: str = "hub"
    repo_id: str = MISSING
    files: list[str] = field(default_factory=list)
    weights_dir: str = MISSING


@dataclass
class ScriptModelConfig(ModelConfig):
    """Weights produced by an imported Python entrypoint (``module:function``)."""

    source: str = "script"
    entrypoint: str = MISSING
    weights_dir: str = MISSING


@dataclass
class ConfigModelConfig(ModelConfig):
    """Model built entirely from config (architecture fields) and saved."""

    source: str = "config"
    weights_dir: str = MISSING


@dataclass
class TeacherModelConfig(ModelConfig):
    """YOLO teacher loaded via Ultralytics by model_id string (auto-downloads)."""

    source: str = "config"
    arch: str = "teacher"
    model_id: str = "yolo11x-seg.pt"
    weights_dir: str = "models/checkpoints/teacher"


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
