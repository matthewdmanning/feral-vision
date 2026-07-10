"""Inference wrapper applying config-driven post-processing to a model.

Wraps a model, calls it, then filters the result by ``cfg.inference`` settings
(score threshold, minimum box area) and optionally averages a horizontal-flip
TTA pass.
"""

from __future__ import annotations

import torch
from omegaconf import DictConfig
from torch import nn

from feral_segmentor.models.base import SegmentationOutput


class Predictor:
    def __init__(self, model: nn.Module, cfg: DictConfig) -> None:
        self.model = model
        self.cfg = cfg

    def _inference_cfg(self) -> DictConfig | None:
        inf = getattr(self.cfg, "inference", None)
        return inf

    def predict(self, image: torch.Tensor) -> SegmentationOutput:
        # The registry/adapter architectures (models.registry.build_model,
        # SourceAdapter.fetch) return a plain nn.Module exposing only
        # forward(), not the predict() -> SegmentationOutput contract this
        # method was written against (that contract belonged to the deleted
        # student/teacher classes). Disabled until a forward()-based
        # SegmentationOutput mapping is designed.
        raise NotImplementedError(
            "Predictor.predict is not wired to the current nn.Module-only "
            "model contract; see comments in this method"
        )
        # inf = self._inference_cfg()
        # tta = bool(getattr(inf, "tta", False)) if inf is not None else False
        #
        # output = self.model.predict(image)
        #
        # if tta:
        #     flipped = torch.flip(image, dims=[-1])
        #     flipped_out = self.model.predict(flipped)
        #     # Average the per-pixel logits of the (un-flipped) flip pass.
        #     avg_logits = (
        #         output.mask_logits + torch.flip(flipped_out.mask_logits, dims=[-1])
        #     ) / 2.0
        #     output = SegmentationOutput(
        #         mask_logits=avg_logits,
        #         boxes=output.boxes,
        #         scores=output.scores,
        #         labels=output.labels,
        #     )
        #
        # threshold = float(getattr(inf, "threshold", 0.5)) if inf is not None else 0.5
        # min_box_area = int(getattr(inf, "min_box_area", 1)) if inf is not None else 1
        #
        # return self._filter(output, threshold, min_box_area)

    @staticmethod
    def _filter(
        output: SegmentationOutput, threshold: float, min_box_area: int
    ) -> SegmentationOutput:
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
