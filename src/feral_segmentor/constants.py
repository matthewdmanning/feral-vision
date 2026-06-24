"""Central numeric/string defaults so no magic numbers leak into logic or schema.

Every tunable that would otherwise appear as a literal in code or as an inline
default in a config dataclass lives here. Import from this module rather than
re-typing a literal.
"""

from __future__ import annotations

# --- Geometry ---------------------------------------------------------------
BOX_COORD_COUNT: int = 4  # bounding boxes are stored xyxy
DEFAULT_IMAGE_SIZE: int = 256  # square side length used for resize/letterbox

# --- Model architecture -----------------------------------------------------
DEFAULT_IN_CHANNELS: int = 3  # RGB
DEFAULT_BASE_CHANNELS: int = 16  # backbone width; doubled per downsample stage
DEFAULT_NUM_CLASSES: int = 2  # background + cat (semantic / pixel-wise logits)

# --- Training ---------------------------------------------------------------
DEFAULT_EPOCHS: int = 1
DEFAULT_LR: float = 1e-4
DEFAULT_BATCH_SIZE: int = 8
DEFAULT_WEIGHT_DECAY: float = 1e-4
DEFAULT_MOMENTUM: float = 0.9
DEFAULT_NUM_WORKERS: int = 0
DEFAULT_OPTIMIZER: str = "adam"
DEFAULT_SCHEDULER: str = "none"
DEFAULT_SCHEDULER_STEP_SIZE: int = 10
DEFAULT_SCHEDULER_GAMMA: float = 0.1

# --- Loss -------------------------------------------------------------------
DEFAULT_DICE_WEIGHT: float = 1.0
DEFAULT_BCE_WEIGHT: float = 1.0
DEFAULT_DISTILL_WEIGHT: float = 0.0  # 0 disables teacher distillation
DEFAULT_DISTILL_TEMPERATURE: float = 1.0
DICE_SMOOTH: float = 1.0  # Laplace smoothing for dice numerator/denominator

# --- Data -------------------------------------------------------------------
DEFAULT_DATA_SOURCE: str = "local"
DEFAULT_VAL_SPLIT: float = 0.2

# --- Augmentation -----------------------------------------------------------
DEFAULT_ROTATE90_K: int = 1  # number of counter-clockwise 90-degree turns
DEFAULT_BRIGHTNESS_SHIFT: float = 0.1  # additive shift on [0, 1] normalized images
DEFAULT_GAMMA: float = 1.2  # gamma correction exponent (>1 darkens midtones)
DEFAULT_MOTION_BLUR_KERNEL: int = 15  # motion blur kernel size (odd, pixels)

# --- Inference / post-processing -------------------------------------------
DEFAULT_DEVICE: str = "cpu"
DEFAULT_MASK_THRESHOLD: float = 0.5  # sigmoid/softmax prob cutoff for foreground
DEFAULT_MIN_BOX_AREA: int = 1  # drop boxes smaller than this (pixels^2)
DEFAULT_TTA: bool = False
