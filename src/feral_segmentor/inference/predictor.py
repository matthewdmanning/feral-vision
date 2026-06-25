"""Inference wrapper applying config-driven post-processing to a model.

Wraps a :class:`SegmentationModel`, calls its ``predict``, then filters the
result by ``cfg.inference`` settings (score threshold, minimum box area) and
optionally averages a horizontal-flip TTA pass.
"""

from __future__ import annotations

import torch
from omegaconf import DictConfig

from feral_segmentor.constants import DEFAULT_MASK_THRESHOLD, DEFAULT_MIN_BOX_AREA
from feral_segmentor.models.base import SegmentationModel, SegmentationOutput


class Predictor:
    def __init__(self, model: SegmentationModel, cfg: DictConfig) -> None:
        self.model = model
        self.cfg = cfg

    def _inference_cfg(self) -> DictConfig | None:
        inf = getattr(self.cfg, "inference", None)
        return inf

    def predict(self, image: torch.Tensor) -> SegmentationOutput:
        inf = self._inference_cfg()
        tta = bool(getattr(inf, "tta", False)) if inf is not None else False

        output = self.model.predict(image)

        if tta:
            flipped = torch.flip(image, dims=[-1])
            flipped_out = self.model.predict(flipped)
            # Average the per-pixel logits of the (un-flipped) flip pass.
            avg_logits = (output.mask_logits + torch.flip(flipped_out.mask_logits, dims=[-1])) / 2.0
            output = SegmentationOutput(
                mask_logits=avg_logits,
                boxes=output.boxes,
                scores=output.scores,
                labels=output.labels,
            )

        threshold = float(getattr(inf, "threshold", DEFAULT_MASK_THRESHOLD)) if inf is not None else DEFAULT_MASK_THRESHOLD
        min_box_area = int(getattr(inf, "min_box_area", DEFAULT_MIN_BOX_AREA)) if inf is not None else DEFAULT_MIN_BOX_AREA

        return self._filter(output, threshold, min_box_area)

    @staticmethod
    def _filter(output: SegmentationOutput, threshold: float, min_box_area: int) -> SegmentationOutput:
        boxes = output.boxes
        if boxes.numel() == 0:
            return output

        widths = boxes[:, 2] - boxes[:, 0]
        heights = boxes[:, 3] - boxes[:, 1]
        areas = widths * heights

        keep = (output.scores >= threshold) & (areas >= min_box_area)

        return SegmentationOutput(
            mask_logits=output.mask_logits,
            boxes=boxes[keep],
            scores=output.scores[keep],
            labels=output.labels[keep],
        )
