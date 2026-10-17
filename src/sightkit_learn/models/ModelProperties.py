from __future__ import annotations

from dataclasses import dataclass, field

from sightkit_learn.tasks import CVTask


@dataclass
class ModelProperties:
    model_outputs: list[CVTask] = field(default_factory=list)
