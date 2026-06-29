from __future__ import annotations

from dataclasses import dataclass, field

from feral_segmentor.tasks import CVTask


@dataclass
class ModelProperties:
    n_classes: int | None = None
    model_outputs: list[CVTask] = field(default_factory=list)
