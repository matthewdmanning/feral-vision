from __future__ import annotations

from dataclasses import dataclass, field

from feral_vision.tasks import CVTask


@dataclass
class ModelProperties:
    model_outputs: list[CVTask] = field(default_factory=list)
