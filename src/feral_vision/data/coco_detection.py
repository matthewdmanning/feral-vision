"""Convert COCO detection annotations into the first-run binary YOLO contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_CAT_CLASS_ID = 0
_NOT_CAT_CLASS_ID = 1


def convert_coco_cat_vs_not_cat_detections(
    annotation_path: str | Path, images_root: str | Path, output_root: str | Path
) -> Path:
    """Use this function to derive binary YOLO detection labels from a COCO animal Artifact."""
    annotation_path = Path(annotation_path)
    images_root = Path(images_root)
    output_root = Path(output_root)

    with annotation_path.open(encoding="utf-8") as handle:
        document: dict[str, Any] = json.load(handle)

    categories = {
        category["id"]: category["name"]
        for category in document.get("categories", [])
        if isinstance(category, dict)
        and isinstance(category.get("id"), int)
        and isinstance(category.get("name"), str)
    }
    images = {
        image["id"]: image
        for image in document.get("images", [])
        if isinstance(image, dict) and isinstance(image.get("id"), int)
    }
    annotations_by_image: dict[int, list[dict[str, Any]]] = {}
    for annotation in document.get("annotations", []):
        if isinstance(annotation, dict) and isinstance(annotation.get("image_id"), int):
            annotations_by_image.setdefault(annotation["image_id"], []).append(
                annotation
            )

    output_root.mkdir(parents=True, exist_ok=True)
    for image_id, image in images.items():
        file_name = image.get("file_name")
        width = image.get("width")
        height = image.get("height")
        if (
            not isinstance(file_name, str)
            or not isinstance(width, int)
            or not isinstance(height, int)
        ):
            raise ValueError(
                f"COCO image {image_id} is missing file_name, width, or height"
            )
        if width <= 0 or height <= 0:
            raise ValueError(f"COCO image {image_id} has non-positive dimensions")
        if not (images_root / file_name).is_file():
            raise FileNotFoundError(f"COCO image is absent from payload: {file_name}")

        lines: list[str] = []
        for annotation in annotations_by_image.get(image_id, []):
            category_name = categories.get(annotation.get("category_id"))
            bbox = annotation.get("bbox")
            if category_name is None or not _valid_bbox(bbox):
                continue
            x, y, box_width, box_height = bbox
            left = max(0.0, x)
            top = max(0.0, y)
            right = min(float(width), x + box_width)
            bottom = min(float(height), y + box_height)
            if right <= left or bottom <= top:
                continue
            class_id = _CAT_CLASS_ID if category_name == "cat" else _NOT_CAT_CLASS_ID
            centre_x = ((left + right) / 2) / width
            centre_y = ((top + bottom) / 2) / height
            normalized_width = (right - left) / width
            normalized_height = (bottom - top) / height
            lines.append(
                f"{class_id} {centre_x:.6f} {centre_y:.6f} "
                f"{normalized_width:.6f} {normalized_height:.6f}"
            )

        label_path = output_root / Path(file_name).with_suffix(".txt")
        label_path.parent.mkdir(parents=True, exist_ok=True)
        label_path.write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )

    (output_root / "names.yaml").write_text(
        "names:\n  0: cat\n  1: not-cat\n", encoding="utf-8"
    )
    return output_root


def _valid_bbox(value: object) -> bool:
    """Use this function to reject malformed COCO boxes before label generation."""
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(isinstance(coordinate, (int, float)) for coordinate in value)
        and value[2] > 0
        and value[3] > 0
    )
