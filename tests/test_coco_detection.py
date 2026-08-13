"""Verify COCO animal annotations become the first-run binary YOLO contract."""

from __future__ import annotations

# stdlib
import json
from pathlib import Path

# project
from feral_vision.data.coco_detection import convert_coco_cat_vs_not_cat_detections


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _write_coco_payload(root: Path, annotations: list[dict[str, object]]) -> Path:
    """Use this function to create a tiny COCO payload with a present source image."""
    images_root = root / "images"
    images_root.mkdir()
    (images_root / "animal.jpg").write_bytes(b"image")
    annotation_path = root / "instances.json"
    annotation_path.write_text(
        json.dumps(
            {
                "categories": [{"id": 1, "name": "cat"}, {"id": 2, "name": "dog"}],
                "images": [
                    {"id": 10, "file_name": "animal.jpg", "width": 100, "height": 50}
                ],
                "annotations": annotations,
            }
        )
    )
    return annotation_path


# ---------------------------------------------------------------------------
# Binary YOLO detection labels
# ---------------------------------------------------------------------------


def test_convert_coco_cat_vs_not_cat_maps_categories_and_normalizes_boxes(
    tmp_path: Path,
) -> None:
    annotation_path = _write_coco_payload(
        tmp_path,
        [
            {"image_id": 10, "category_id": 1, "bbox": [10, 5, 20, 10]},
            {"image_id": 10, "category_id": 2, "bbox": [50, 20, 20, 10]},
        ],
    )

    output_root = convert_coco_cat_vs_not_cat_detections(
        annotation_path, tmp_path / "images", tmp_path / "labels"
    )

    assert (output_root / "animal.txt").read_text().splitlines() == [
        "0 0.200000 0.200000 0.200000 0.200000",
        "1 0.600000 0.500000 0.200000 0.200000",
    ]
    assert (
        output_root / "names.yaml"
    ).read_text() == "names:\n  0: cat\n  1: not-cat\n"


def test_convert_coco_cat_vs_not_cat_omits_invalid_boxes_but_writes_label_file(
    tmp_path: Path,
) -> None:
    annotation_path = _write_coco_payload(
        tmp_path,
        [
            {"image_id": 10, "category_id": 1, "bbox": [10, 5, 0, 10]},
            {"image_id": 10, "category_id": 2, "bbox": [200, 5, 10, 10]},
        ],
    )

    output_root = convert_coco_cat_vs_not_cat_detections(
        annotation_path, tmp_path / "images", tmp_path / "labels"
    )

    assert (output_root / "animal.txt").read_text() == ""
