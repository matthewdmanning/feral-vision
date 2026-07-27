"""Download a bounded animal subset of COCO 2017 through FiftyOne.

The downloaded images and annotations are managed by FiftyOne's dataset zoo.
"""

from __future__ import annotations

from pathlib import Path

COCO_ANIMAL_CLASSES = [
    "bird",
    "cat",
    "dog",
    "horse",
    "sheep",
    "cow",
    "elephant",
    "bear",
    "zebra",
    "giraffe",
]


def pull_coco_train2017(*, max_epochs: int, batch_size: int) -> object:
    """Load a training-sized COCO 2017 animal detection dataset from FiftyOne."""
    if max_epochs < 1 or batch_size < 1:
        raise ValueError("max_epochs and batch_size must both be positive")

    import fiftyone.zoo

    max_samples = max_epochs * batch_size
    return fiftyone.zoo.load_zoo_dataset(
        "coco-2017",
        split="train",
        label_types=["detections"],
        classes=COCO_ANIMAL_CLASSES,
        max_samples=max_samples,
    )


def export_coco_train2017(
    *, max_epochs: int, batch_size: int, export_dir: Path
) -> Path:
    """Export the bounded COCO subset using the canonical image/annotation layout."""
    import fiftyone as fo

    if export_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing export directory: {export_dir}")
    dataset = pull_coco_train2017(max_epochs=max_epochs, batch_size=batch_size)
    dataset.export(
        export_dir=str(export_dir),
        dataset_type=fo.types.COCODetectionDataset,
        label_field="ground_truth",
        export_media="copy",
    )
    (export_dir / "data").rename(export_dir / "images")
    annotations = export_dir / "annotations"
    annotations.mkdir()
    (export_dir / "labels.json").rename(annotations / "instances.json")
    return export_dir
