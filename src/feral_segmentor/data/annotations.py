"""Annotation types for the feral-segmentor dataset pipeline."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np


class Annotation(abc.ABC):
    """Base for all annotation types. Subclasses hold task-specific data."""

    @abc.abstractmethod
    def load(self) -> "Annotation":
        """Resolve any lazy references and return self with data populated."""
        ...


@dataclass
class MaskAnnotation(Annotation):
    """Pixel-level semantic segmentation mask (CVTask.SEG_SEMANTIC).

    ``mask`` is an (H, W) uint8 array of class ids. Loaded lazily from
    ``path`` on first access if ``mask`` is None.
    """

    path: Path
    mask: np.ndarray | None = field(default=None, repr=False)

    def load(self) -> "MaskAnnotation":
        if self.mask is None:
            import cv2

            self.mask = cv2.imread(str(self.path), cv2.IMREAD_GRAYSCALE)
            if self.mask is None:
                raise FileNotFoundError(f"failed to read mask: {self.path}")
        return self


@dataclass
class BBoxAnnotation(Annotation):
    """Bounding box instance annotation (CVTask.SEG_INSTANCE).

    ``boxes`` is an (N, 4) float32 array in normalised xyxy format.
    ``class_ids`` is an (N,) int array.
    Loaded lazily from YOLO-format ``.txt`` at ``path``.
    """

    path: Path
    boxes: np.ndarray | None = field(default=None, repr=False)
    class_ids: np.ndarray | None = field(default=None, repr=False)

    def load(self) -> "BBoxAnnotation":
        if self.boxes is None:
            rows = Path(self.path).read_text().splitlines()
            if not rows:
                self.boxes = np.zeros((0, 4), dtype=np.float32)
                self.class_ids = np.zeros(0, dtype=np.int64)
                return self
            class_ids, boxes = [], []
            for row in rows:
                parts = row.split()
                class_ids.append(int(parts[0]))
                boxes.append([float(x) for x in parts[1:5]])
            self.class_ids = np.array(class_ids, dtype=np.int64)
            self.boxes = np.array(boxes, dtype=np.float32)
        return self


@dataclass
class ClassificationAnnotation(Annotation):
    """Single classification head annotation (CVTask.CLASSIFICATION).

    ``name``       — classifier name matching the appearance schema key.
    ``input_type`` — "radio" (single choice) or "checkbox" (multi-choice).
    ``value``      — selected label(s); str for radio, list[str] for checkbox.
    """

    name: str
    input_type: Literal["radio", "checkbox"]
    value: str | list[str]

    def load(self) -> "ClassificationAnnotation":
        return self  # already in memory


@dataclass
class DetectionAnnotation(Annotation):
    """Binary present/absent detection (CVTask.DETECTION)."""

    present: bool

    def load(self) -> "DetectionAnnotation":
        return self


@dataclass
class PoseAnnotation(Annotation):
    """Keypoint pose annotation (CVTask.POSE). Not yet implemented."""

    path: Path

    def load(self) -> "PoseAnnotation":
        raise NotImplementedError("PoseAnnotation loading not yet implemented")
