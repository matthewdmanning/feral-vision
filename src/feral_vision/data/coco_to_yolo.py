"""Convert COCO instance segmentation annotations to YOLO segmentation format.

Output per image is a .txt file with one line per annotation::

    <class_id> <x1> <y1> <x2> <y2> ... <xn> <yn>

Coordinates are normalised to [0, 1] by image width/height.

Usage (offline, run once before pushing to GCS)::

    python -m feral_vision.data.coco_to_yolo \\
        --ann data/raw/annotations/coco_train2017/instances_train2017_animals.json \\
        --out data/raw/labels/coco_train2017/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from feral_vision.utils import get_logger

logger = get_logger(__name__)


def convert(ann_path: str | Path, out_dir: str | Path) -> None:
    """Write YOLO .txt label files from a COCO annotations JSON.

    Parameters
    ----------
    ann_path:
        Path to the filtered COCO JSON (e.g. instances_train2017_animals.json).
    out_dir:
        Directory to write .txt files into. Created if absent.
    """
    ann_path = Path(ann_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with ann_path.open() as f:
        coco = json.load(f)

    # Build stable category index: sorted by cat id so class 0..N-1 is deterministic.
    sorted_cats = sorted(coco["categories"], key=lambda c: c["id"])
    cat_id_to_class = {c["id"]: idx for idx, c in enumerate(sorted_cats)}
    logger.info(
        "class mapping: %s",
        {c["name"]: cat_id_to_class[c["id"]] for c in sorted_cats},
    )

    # Index image metadata by id.
    images = {img["id"]: img for img in coco["images"]}

    # Group annotations by image id.
    anns_by_image: dict[int, list[dict]] = {}
    for ann in coco["annotations"]:
        anns_by_image.setdefault(ann["image_id"], []).append(ann)

    skipped = 0
    written = 0
    for image_id, anns in anns_by_image.items():
        img = images[image_id]
        w, h = img["width"], img["height"]
        stem = Path(img["file_name"]).stem
        lines: list[str] = []

        for ann in anns:
            cls = cat_id_to_class[ann["category_id"]]
            segs = ann.get("segmentation", [])
            if not segs or ann.get("iscrowd", 0):
                skipped += 1
                continue
            # Use the longest polygon if multiple segments present.
            poly = max(segs, key=len)
            if len(poly) < 6:
                skipped += 1
                continue
            # Normalise flat [x1,y1,x2,y2,...] list.
            coords = []
            for i in range(0, len(poly) - 1, 2):
                coords.append(f"{poly[i] / w:.6f}")
                coords.append(f"{poly[i + 1] / h:.6f}")
            lines.append(f"{cls} {' '.join(coords)}")

        if lines:
            (out_dir / f"{stem}.txt").write_text("\n".join(lines))
            written += 1

    logger.info("wrote %d label files, skipped %d annotations", written, skipped)


def _build_names_yaml(ann_path: str | Path, out_path: str | Path) -> None:
    """Write a names.yaml listing class_id -> name for reference."""
    with Path(ann_path).open() as f:
        coco = json.load(f)
    sorted_cats = sorted(coco["categories"], key=lambda c: c["id"])
    lines = ["names:"]
    for idx, c in enumerate(sorted_cats):
        lines.append(f"  {idx}: {c['name']}")
    Path(out_path).write_text("\n".join(lines) + "\n")
    logger.info("wrote class names to %s", out_path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ann", required=True, help="Path to COCO annotations JSON")
    parser.add_argument(
        "--out", required=True, help="Output directory for YOLO .txt files"
    )
    parser.add_argument(
        "--names",
        default=None,
        help="Optional path to write names.yaml (class index reference)",
    )
    args = parser.parse_args()
    convert(args.ann, args.out)
    if args.names:
        _build_names_yaml(args.ann, args.names)


if __name__ == "__main__":
    main()
