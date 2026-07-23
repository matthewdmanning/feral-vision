"""Verify annotation loaders materialize their documented on-disk contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from feral_vision.data.annotations import (
    BBoxAnnotation,
    MaskAnnotation,
    PoseAnnotation,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
ANNOTATIONS_DIR = FIXTURES_DIR / "annotations"

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _write_yolo_txt(
    path: Path, rows: list[tuple[int, float, float, float, float]]
) -> None:
    """Write a YOLO-format annotation file with one ``class x y w h`` row per line."""
    lines = [" ".join(str(v) for v in row) for row in rows]
    path.write_text("\n".join(lines))


def _read_mask(path: Path) -> np.ndarray:
    """Read a fixture mask through Pillow for an independent expected value."""
    with Image.open(path) as image:
        return np.asarray(image.convert("L"))


@pytest.fixture(
    params=[
        pytest.param("american_bulldog_103", id="portrait"),
        pytest.param("beagle_203", id="landscape"),
        pytest.param("chihuahua_104", id="small"),
    ]
)
def mask_annotation_path(request: pytest.FixtureRequest) -> Path:
    """Provide fixture masks with varied dimensions for lazy loading."""
    return ANNOTATIONS_DIR / f"{request.param}.png"


@pytest.fixture(params=[(1, 3), (3, 10), (10, 1)])
def preloaded_mask(request: pytest.FixtureRequest) -> np.ndarray:
    """Provide pre-materialized masks across representative dimensions."""
    return np.full(request.param, 7, dtype=np.uint8)


@pytest.fixture(
    params=[
        pytest.param([], id="empty"),
        pytest.param([(2, 0.1, 0.2, 0.3, 0.4)], id="one-box"),
        pytest.param(
            [
                (0, 0.1, 0.2, 0.3, 0.4),
                (1, 0.2, 0.3, 0.4, 0.5),
                (2, 0.3, 0.4, 0.5, 0.6),
            ],
            id="three-boxes",
        ),
    ]
)
def yolo_rows(
    request: pytest.FixtureRequest,
) -> list[tuple[int, float, float, float, float]]:
    """Provide YOLO row counts covering empty and populated annotations."""
    return request.param


# ---------------------------------------------------------------------------
# MaskAnnotation — lazy mask loading
# ---------------------------------------------------------------------------


def test_mask_annotation_load_materializes_fixture_pixels(
    mask_annotation_path: Path,
) -> None:
    expected_mask = _read_mask(mask_annotation_path)
    ann = MaskAnnotation(path=mask_annotation_path)

    result = ann.load()

    assert result is ann
    assert ann.mask is not None
    np.testing.assert_array_equal(ann.mask, expected_mask)


def test_mask_annotation_load_keeps_preloaded_mask(
    preloaded_mask: np.ndarray,
) -> None:
    ann = MaskAnnotation(path=Path("does/not/exist.png"), mask=preloaded_mask)

    result = ann.load()

    assert result is ann
    assert ann.mask is not None
    np.testing.assert_array_equal(ann.mask, preloaded_mask)


def test_mask_annotation_load_missing_file_raises(tmp_path: Path) -> None:
    ann = MaskAnnotation(path=tmp_path / "missing.png")

    with pytest.raises(FileNotFoundError, match="missing.png"):
        ann.load()


# ---------------------------------------------------------------------------
# BBoxAnnotation — lazy YOLO loading
# ---------------------------------------------------------------------------


def test_bbox_annotation_load_parses_yolo_rows(
    tmp_path: Path, yolo_rows: list[tuple[int, float, float, float, float]]
) -> None:
    path = tmp_path / "boxes.txt"
    _write_yolo_txt(path, yolo_rows)

    ann = BBoxAnnotation(path=path)
    result = ann.load()

    expected_boxes = np.asarray(
        [row[1:] for row in yolo_rows], dtype=np.float32
    ).reshape(-1, 4)
    expected_classes = np.asarray([row[0] for row in yolo_rows], dtype=np.int64)
    assert result is ann
    assert ann.boxes is not None
    assert ann.class_ids is not None
    np.testing.assert_allclose(ann.boxes, expected_boxes)
    np.testing.assert_array_equal(ann.class_ids, expected_classes)


def test_bbox_annotation_load_keeps_preloaded_values() -> None:
    preset_boxes = np.array([[0.1, 0.1, 0.2, 0.2]], dtype=np.float32)
    preset_classes = np.array([5], dtype=np.int64)
    ann = BBoxAnnotation(
        path=Path("does/not/exist.txt"), boxes=preset_boxes, class_ids=preset_classes
    )

    result = ann.load()

    assert result is ann
    assert ann.boxes is not None
    assert ann.class_ids is not None
    np.testing.assert_array_equal(ann.boxes, preset_boxes)
    np.testing.assert_array_equal(ann.class_ids, preset_classes)


# ---------------------------------------------------------------------------
# PoseAnnotation — not yet implemented
# ---------------------------------------------------------------------------


def test_pose_annotation_load_reports_unsupported_format(tmp_path: Path) -> None:
    ann = PoseAnnotation(path=tmp_path / "pose.json")

    with pytest.raises(NotImplementedError, match="not yet implemented"):
        ann.load()
