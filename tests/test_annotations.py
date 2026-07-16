"""Contract tests for the Annotation subclasses in feral_vision.data.annotations."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from feral_vision.data.annotations import (
    Annotation,
    BBoxAnnotation,
    ClassificationAnnotation,
    DetectionAnnotation,
    MaskAnnotation,
    PoseAnnotation,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ANNOTATIONS_DIR = FIXTURES_DIR / "annotations"

_FIXTURE_MASK_STEMS = [
    "american_bulldog_103",
    "beagle_203",
    "Bengal_48",
    "British_Shorthair_127",
    "chihuahua_104",
    "Egyptian_Mau_149",
    "Ragdoll_139",
    "scottish_terrier_166",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yolo_txt(
    path: Path, rows: list[tuple[int, float, float, float, float]]
) -> None:
    """Write a YOLO-format annotation file with one ``class x y w h`` row per line."""
    lines = [" ".join(str(v) for v in row) for row in rows]
    path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Annotation — abstract base contract
# ---------------------------------------------------------------------------


def test_annotation_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        Annotation()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# MaskAnnotation — loads a real mask file from disk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("stem", _FIXTURE_MASK_STEMS)
def test_mask_annotation_load_reads_fixture_mask(stem):
    ann = MaskAnnotation(path=ANNOTATIONS_DIR / f"{stem}.png")
    result = ann.load()

    assert result is ann
    assert isinstance(ann.mask, np.ndarray)
    assert ann.mask.dtype == np.uint8
    assert ann.mask.ndim == 2


def test_mask_annotation_load_does_not_reread_when_already_populated():
    preset_mask = np.full((4, 4), 7, dtype=np.uint8)
    ann = MaskAnnotation(path=Path("does/not/exist.png"), mask=preset_mask)

    ann.load()

    assert ann.mask is preset_mask


def test_mask_annotation_load_missing_file_raises(tmp_path):
    ann = MaskAnnotation(path=tmp_path / "missing.png")
    with pytest.raises(FileNotFoundError, match="missing.png"):
        ann.load()


# ---------------------------------------------------------------------------
# BBoxAnnotation — parses a real YOLO .txt file from disk
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("n_boxes", [0, 1, 3])
def test_bbox_annotation_load_parses_rows(tmp_path, n_boxes):
    rows = [(i % 3, 0.1 * i, 0.2 * i, 0.3, 0.4) for i in range(n_boxes)]
    path = tmp_path / "boxes.txt"
    _write_yolo_txt(path, rows)

    ann = BBoxAnnotation(path=path).load()

    assert ann.boxes.shape == (n_boxes, 4)
    assert ann.boxes.dtype == np.float32
    assert ann.class_ids.shape == (n_boxes,)
    assert ann.class_ids.dtype == np.int64
    if n_boxes:
        expected_boxes = np.array([row[1:] for row in rows], dtype=np.float32)
        expected_classes = np.array([row[0] for row in rows], dtype=np.int64)
        np.testing.assert_allclose(ann.boxes, expected_boxes)
        np.testing.assert_array_equal(ann.class_ids, expected_classes)


def test_bbox_annotation_load_does_not_reparse_when_already_populated():
    preset_boxes = np.array([[0.1, 0.1, 0.2, 0.2]], dtype=np.float32)
    preset_classes = np.array([5], dtype=np.int64)
    ann = BBoxAnnotation(
        path=Path("does/not/exist.txt"), boxes=preset_boxes, class_ids=preset_classes
    )

    ann.load()

    assert ann.boxes is preset_boxes
    assert ann.class_ids is preset_classes


# ---------------------------------------------------------------------------
# ClassificationAnnotation — already-in-memory contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "input_type,value",
    [("radio", "black"), ("checkbox", ["black", "white"])],
)
def test_classification_annotation_load_returns_self_unchanged(input_type, value):
    ann = ClassificationAnnotation(
        name="coat_color", input_type=input_type, value=value
    )

    result = ann.load()

    assert result is ann
    assert ann.name == "coat_color"
    assert ann.input_type == input_type
    assert ann.value == value


# ---------------------------------------------------------------------------
# DetectionAnnotation — already-in-memory contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("present", [True, False])
def test_detection_annotation_load_returns_self_unchanged(present):
    ann = DetectionAnnotation(present=present)

    result = ann.load()

    assert result is ann
    assert ann.present is present


# ---------------------------------------------------------------------------
# PoseAnnotation — not yet implemented
# ---------------------------------------------------------------------------


def test_pose_annotation_load_raises_not_implemented(tmp_path):
    ann = PoseAnnotation(path=tmp_path / "pose.json")
    with pytest.raises(NotImplementedError):
        ann.load()
