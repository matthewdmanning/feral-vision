"""Compatibility imports for the former combined detection adapter."""

from __future__ import annotations

from typing import Any, Iterable

import torch
from torch import nn

from sightkit_learn.training.detection import (
    DetectionBatch,
    collate_detection,
    detection_loss,
)


class DetectionTaskAdapter:
    """Preserve existing callers while collation and loss remain independent.

    Parameters
    ----------
    num_classes : int
        Number of foreground classes accepted by the collator.
    """

    def __init__(self, *, num_classes: int) -> None:
        self.num_classes = num_classes

    def collate(
        self, samples: Iterable[tuple[torch.Tensor, list[Any]]]
    ) -> DetectionBatch:
        """Collate detection samples using the standalone collator."""
        return collate_detection(samples, num_classes=self.num_classes)

    def loss(
        self, model: nn.Module, batch: DetectionBatch
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        """Compute the unchanged native-assignment detection objective."""
        return detection_loss(model, batch)
