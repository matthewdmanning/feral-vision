"""Code-level constants only — no tunable hyperparameters.

Tunables (image size, LR, batch size, thresholds, etc.) live in
``conf/`` YAML files and are accessed through Hydra config objects.
"""

from __future__ import annotations

# --- Geometry ---------------------------------------------------------------
BOX_COORD_COUNT: int = 4  # bounding boxes are stored xyxy

# --- Loss -------------------------------------------------------------------
DICE_SMOOTH: float = 1.0  # Laplace smoothing for dice numerator/denominator
