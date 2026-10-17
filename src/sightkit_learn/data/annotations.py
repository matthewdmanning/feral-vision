"""Annotation data types for the feral-vision dataset pipeline."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np


class Annotation(abc.ABC):
    """Base class for all task-specific annotation types.

    Subclasses hold task-specific data and implement :meth:`load` to
    materialise any lazy references from disk.
    """

    @abc.abstractmethod
    def load(self) -> Annotation:
        """Resolve any lazy references and return self with data populated.

        Returns
        -------
        Annotation
            Self, with all data fields populated.
        """
        ...


@dataclass
class MaskAnnotation(Annotation):
    """Pixel-level semantic segmentation mask (CVTask.SEG_SEMANTIC).

    Parameters
    ----------
    path : Path
        Path to the mask image file.
    mask : numpy.ndarray, optional
        ``(H, W)`` uint8 array of class ids. Populated by :meth:`load`.
    """

    path: Path
    mask: np.ndarray | None = field(default=None, repr=False)

    def load(self) -> MaskAnnotation:
        """Load the mask from disk into :attr:`mask`.

        Returns
        -------
        MaskAnnotation
            Self with :attr:`mask` populated as an ``(H, W)`` uint8 array.

        Raises
        ------
        FileNotFoundError
            If the mask file cannot be read by OpenCV.
        """
        if self.mask is None:
            import cv2

            self.mask = cv2.imread(str(self.path), cv2.IMREAD_GRAYSCALE)
            if self.mask is None:
                raise FileNotFoundError(f"failed to read mask: {self.path}")
        return self


@dataclass
class BBoxAnnotation(Annotation):
    """Bounding box instance annotation in YOLO format (CVTask.SEG_INSTANCE).

    Parameters
    ----------
    path : Path
        Path to the YOLO-format ``.txt`` file.
    boxes : numpy.ndarray, optional
        ``(N, 4)`` float32 array of normalised xywh boxes. Populated by :meth:`load`.
    class_ids : numpy.ndarray, optional
        ``(N,)`` int64 array of class indices. Populated by :meth:`load`.
    """

    path: Path
    boxes: np.ndarray | None = field(default=None, repr=False)
    class_ids: np.ndarray | None = field(default=None, repr=False)

    def load(self) -> BBoxAnnotation:
        """Load boxes and class ids from a YOLO-format ``.txt`` file.

        Returns
        -------
        BBoxAnnotation
            Self with :attr:`boxes` and :attr:`class_ids` populated.
        """
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

    Parameters
    ----------
    name : str
        Classifier name matching the appearance schema key.
    input_type : {"radio", "checkbox"}
        ``"radio"`` for single-choice, ``"checkbox"`` for multi-choice.
    value : str or list[str]
        Selected label(s); ``str`` for radio, ``list[str]`` for checkbox.
    """

    name: str
    input_type: Literal["radio", "checkbox"]
    value: str | list[str]

    def load(self) -> ClassificationAnnotation:
        """Return self; classification annotations are already in memory.

        Returns
        -------
        ClassificationAnnotation
            Self, unchanged.
        """
        return self


@dataclass
class DetectionAnnotation(Annotation):
    """Binary present / absent detection annotation (CVTask.DETECTION).

    Parameters
    ----------
    present : bool
        Whether the target object is present in the image.
    """

    present: bool

    def load(self) -> DetectionAnnotation:
        """Return self; detection annotations are already in memory.

        Returns
        -------
        DetectionAnnotation
            Self, unchanged.
        """
        return self


@dataclass
class PoseAnnotation(Annotation):
    """Keypoint pose annotation (CVTask.POSE). Not yet implemented.

    Parameters
    ----------
    path : Path
        Path to the pose annotation file.
    """

    path: Path

    def load(self) -> PoseAnnotation:
        """Raise NotImplementedError; pose loading is not yet implemented.

        Raises
        ------
        NotImplementedError
            Always.
        """
        raise NotImplementedError("PoseAnnotation loading not yet implemented")
