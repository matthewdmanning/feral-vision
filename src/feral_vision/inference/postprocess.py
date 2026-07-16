"""Mask post-processing: binary cleanup and box extraction.

Operates on torch tensors (CPU) but uses cv2 for connected-components and
morphology where that is simplest. All numeric defaults come from
:mod:`feral_vision.constants`.
"""

from __future__ import annotations

import cv2
import numpy as np
import torch

from feral_vision.constants import BOX_COORD_COUNT

# Morphology kernel side length for the open/close cleanup pass.
MORPH_KERNEL_SIZE: int = 3


def _to_bool_hw(mask: torch.Tensor) -> torch.Tensor:
    """Coerce a mask to a boolean (H, W) tensor on CPU."""
    if mask.dim() != 2:
        raise ValueError(f"expected a 2D (H, W) mask, got shape {tuple(mask.shape)}")
    return mask.detach().to("cpu").bool()


def clean_mask(mask: torch.Tensor) -> torch.Tensor:
    """Morphologically clean a binary foreground mask.

    Applies an opening (remove specks) followed by a closing (fill pinholes)
    using a small square kernel. Returns a boolean (H, W) tensor.
    """
    bool_mask = _to_bool_hw(mask)
    np_mask = bool_mask.numpy().astype(np.uint8)
    kernel = np.ones((MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE), dtype=np.uint8)
    opened = cv2.morphologyEx(np_mask, cv2.MORPH_OPEN, kernel)
    closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)
    return torch.from_numpy(closed.astype(bool))


def masks_to_boxes(mask: torch.Tensor, min_box_area: int = 1) -> torch.Tensor:
    """Derive xyxy boxes from a binary foreground mask via connected components.

    Each connected blob in the (H, W) boolean mask becomes one box. Boxes with
    area (w * h) below ``min_box_area`` are dropped. Returns a float tensor of
    shape ``(N, BOX_COORD_COUNT)``; ``N`` may be 0.
    """
    bool_mask = _to_bool_hw(mask)
    np_mask = bool_mask.numpy().astype(np.uint8)

    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(
        np_mask, connectivity=8
    )

    boxes: list[list[float]] = []
    # Label 0 is the background component; skip it.
    for label in range(1, num_labels):
        x = int(stats[label, cv2.CC_STAT_LEFT])
        y = int(stats[label, cv2.CC_STAT_TOP])
        w = int(stats[label, cv2.CC_STAT_WIDTH])
        h = int(stats[label, cv2.CC_STAT_HEIGHT])
        if w * h < min_box_area:
            continue
        # xyxy with exclusive far edge expressed as inclusive+1 -> x+w, y+h.
        boxes.append([float(x), float(y), float(x + w), float(y + h)])

    if not boxes:
        return torch.zeros((0, BOX_COORD_COUNT), dtype=torch.float32)
    return torch.tensor(boxes, dtype=torch.float32)
