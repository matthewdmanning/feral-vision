from __future__ import annotations

from pathlib import Path

import torch.nn as nn
from ultralytics import YOLO


class TeacherModel(nn.Module):
    """YOLOv11x-seg teacher loaded via Ultralytics."""

    def __init__(self, model_id: str = "yolo11x-seg.pt"):
        super().__init__()
        self.yolo = YOLO(model_id)

    @classmethod
    def from_config(cls, cfg) -> "TeacherModel":
        return cls(model_id=str(cfg.get("model_id", "yolo11x-seg.pt")))

    @classmethod
    def from_path(cls, path: str | Path) -> "TeacherModel":
        obj = cls.__new__(cls)
        super(TeacherModel, obj).__init__()
        obj.yolo = YOLO(str(path))
        return obj

    def forward(self, x):
        return self.yolo(x)
