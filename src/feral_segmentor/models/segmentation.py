"""Small encoder/decoder CNN student segmenter.

A compact U-Net-ish architecture: two downsampling conv blocks (doubling the
channel width each time) followed by two upsampling blocks, producing per-pixel
class logits at the input resolution. Implements both ``nn.Module.forward`` and
the project's :class:`SegmentationModel.predict` contract.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from omegaconf import DictConfig
from torch import nn

from feral_segmentor.constants import (
    DEFAULT_BASE_CHANNELS,
    DEFAULT_IN_CHANNELS,
    DEFAULT_MASK_THRESHOLD,
    DEFAULT_MIN_BOX_AREA,
    DEFAULT_NUM_CLASSES,
)
from feral_segmentor.inference.postprocess import masks_to_boxes
from feral_segmentor.models.base import SegmentationModel, SegmentationOutput

# Index of the background class in the per-pixel softmax distribution.
BACKGROUND_CLASS: int = 0


def _conv_block(in_ch: int, out_ch: int) -> nn.Sequential:
    """Two 3x3 conv + BN + ReLU layers preserving spatial size."""
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, kernel_size=3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, kernel_size=3, padding=1),
        nn.BatchNorm2d(out_ch),
        nn.ReLU(inplace=True),
    )


class StudentSegmenter(nn.Module, SegmentationModel):
    """Compact segmentation network producing (B, num_classes, H, W) logits."""

    def __init__(
        self,
        in_channels: int = DEFAULT_IN_CHANNELS,
        base_channels: int = DEFAULT_BASE_CHANNELS,
        num_classes: int = DEFAULT_NUM_CLASSES,
    ) -> None:
        super().__init__()
        self.in_channels = in_channels
        self.base_channels = base_channels
        self.num_classes = num_classes

        c1 = base_channels
        c2 = base_channels * 2

        # Encoder: two downsampling stages.
        self.enc1 = _conv_block(in_channels, c1)
        self.enc2 = _conv_block(c1, c2)
        self.pool = nn.MaxPool2d(kernel_size=2, stride=2)

        # Decoder: two upsampling stages back to input resolution.
        self.up2 = nn.ConvTranspose2d(c2, c1, kernel_size=2, stride=2)
        self.dec2 = _conv_block(c1, c1)
        self.up1 = nn.ConvTranspose2d(c1, c1, kernel_size=2, stride=2)
        self.dec1 = _conv_block(c1, c1)

        self.head = nn.Conv2d(c1, num_classes, kernel_size=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, w = x.shape[-2], x.shape[-1]

        e1 = self.enc1(x)          # (B, c1, H, W)
        e2 = self.enc2(self.pool(e1))  # (B, c2, H/2, W/2)
        bottom = self.pool(e2)     # (B, c2, H/4, W/4)

        d2 = self.dec2(self.up2(bottom))  # (B, c1, ~H/2, ~W/2)
        d1 = self.dec1(self.up1(d2))      # (B, c1, ~H, ~W)

        logits = self.head(d1)
        # Guard against odd input dims where transposed conv under/overshoots.
        if logits.shape[-2] != h or logits.shape[-1] != w:
            logits = F.interpolate(logits, size=(h, w), mode="bilinear", align_corners=False)
        return logits

    @torch.no_grad()
    def predict(self, image: torch.Tensor) -> SegmentationOutput:
        """Run inference on a single (C, H, W) image tensor."""
        was_training = self.training
        self.eval()
        try:
            batched = image.unsqueeze(0)              # (1, C, H, W)
            logits = self.forward(batched)            # (1, num_classes, H, W)
            probs = torch.softmax(logits, dim=1)[0]   # (num_classes, H, W)

            # Foreground probability = 1 - P(background).
            fg_prob = 1.0 - probs[BACKGROUND_CLASS]   # (H, W)
            fg_mask = fg_prob >= DEFAULT_MASK_THRESHOLD

            boxes = masks_to_boxes(fg_mask, min_box_area=DEFAULT_MIN_BOX_AREA)

            scores_list: list[float] = []
            labels_list: list[int] = []
            # Per-pixel dominant class, used to label each box.
            class_map = probs.argmax(dim=0)           # (H, W)
            for box in boxes:
                x1, y1, x2, y2 = (int(v) for v in box.tolist())
                region_prob = fg_prob[y1:y2, x1:x2]
                region_mask = fg_mask[y1:y2, x1:x2]
                if region_mask.any():
                    scores_list.append(float(region_prob[region_mask].mean()))
                    region_classes = class_map[y1:y2, x1:x2][region_mask]
                    labels_list.append(int(torch.mode(region_classes).values))
                else:
                    scores_list.append(float(region_prob.mean()) if region_prob.numel() else 0.0)
                    labels_list.append(BACKGROUND_CLASS)

            scores = torch.tensor(scores_list, dtype=torch.float32)
            labels = torch.tensor(labels_list, dtype=torch.long)

            return SegmentationOutput(
                mask_logits=logits[0],  # (num_classes, H, W)
                boxes=boxes,
                scores=scores,
                labels=labels,
            )
        finally:
            self.train(was_training)

    @classmethod
    def from_config(cls, cfg: DictConfig) -> StudentSegmenter:
        """Build from a model DictConfig reading arch fields."""
        return cls(
            in_channels=int(cfg.in_channels),
            base_channels=int(cfg.base_channels),
            num_classes=int(cfg.num_classes),
        )
