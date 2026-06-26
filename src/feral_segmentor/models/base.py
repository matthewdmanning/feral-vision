from __future__ import annotations

from dataclasses import dataclass

import torch


@dataclass
class SegmentationOutput:
    """Unified prediction contract for every segmentation model.

    Carries both representations the project needs:
      * ``mask_logits`` — pixel-wise class logits, shape ``(num_classes, H, W)``
        (un-normalised; apply softmax/sigmoid downstream).
      * ``boxes`` — bounding boxes in xyxy, shape ``(N, 4)``.
      * ``scores`` — per-box confidence, shape ``(N,)``.
      * ``labels`` — per-box class index, shape ``(N,)``.

    Boxes may be derived from the mask (connected components) or from a
    dedicated detection head; the contract is identical either way.
    """

    mask_logits: torch.Tensor
    boxes: torch.Tensor
    scores: torch.Tensor
    labels: torch.Tensor
