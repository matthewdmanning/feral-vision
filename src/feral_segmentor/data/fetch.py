"""Data acquisition for the fetch DVC stage.

For the ``local`` source this just resolves and validates a directory already on
disk. The ``coco`` source downloads COCO train2017 images filtered to animal
supercategory and saves them under ``<root>/images/coco_train2017/`` with the
filtered annotations JSON under ``<root>/annotations/coco_train2017/``.
"""

from __future__ import annotations

import io
import json
import urllib.request
import zipfile
from pathlib import Path

import hydra
from omegaconf import DictConfig

from feral_segmentor.constants import (
    COCO_ANNOTATIONS_URL,
    COCO_IMAGE_URL_TEMPLATE,
    COCO_SUPERCATEGORY_FILTER,
    DEFAULT_DATA_SOURCE,
)
from feral_segmentor.utils import get_logger

logger = get_logger(__name__)

# Output subdirectory names under data root.
_IMAGES_SUBDIR = "images/coco_train2017"
_ANNOTATIONS_SUBDIR = "annotations/coco_train2017"
_ANNOTATIONS_FILENAME = "instances_train2017_animals.json"


def fetch_coco(root: str = "data") -> tuple[Path, Path]:
    """Download COCO train2017 images for animal supercategory.

    Downloads the official COCO 2017 instance annotations, filters to images
    that contain at least one annotation whose category belongs to the
    ``"animal"`` supercategory, then downloads those images.

    Parameters
    ----------
    root:
        Local data root. Images land in ``<root>/images/coco_train2017/`` and
        the filtered annotations JSON in
        ``<root>/annotations/coco_train2017/instances_train2017_animals.json``.

    Returns
    -------
    tuple[Path, Path]
        ``(images_dir, annotations_path)``
    """
    root_path = Path(root).resolve()
    images_dir = root_path / _IMAGES_SUBDIR
    ann_dir = root_path / _ANNOTATIONS_SUBDIR
    images_dir.mkdir(parents=True, exist_ok=True)
    ann_dir.mkdir(parents=True, exist_ok=True)

    ann_out = ann_dir / _ANNOTATIONS_FILENAME

    # --- Step 1: fetch + parse annotations -----------------------------------
    if ann_out.exists():
        logger.info("annotations already present: %s", ann_out)
        with ann_out.open() as f:
            filtered = json.load(f)
    else:
        logger.info("downloading COCO annotations from %s", COCO_ANNOTATIONS_URL)
        with urllib.request.urlopen(COCO_ANNOTATIONS_URL) as resp:  # noqa: S310
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            # The zip contains annotations/instances_train2017.json
            ann_name = "annotations/instances_train2017.json"
            with zf.open(ann_name) as f:
                full = json.load(f)

        # Filter categories to the animal supercategory.
        animal_cat_ids = {
            c["id"]
            for c in full["categories"]
            if c["supercategory"] == COCO_SUPERCATEGORY_FILTER
        }
        logger.info(
            "animal category ids (%d): %s",
            len(animal_cat_ids),
            sorted(animal_cat_ids),
        )

        # Keep only annotations that belong to animal categories.
        animal_anns = [
            a for a in full["annotations"] if a["category_id"] in animal_cat_ids
        ]
        animal_image_ids = {a["image_id"] for a in animal_anns}
        animal_images = [i for i in full["images"] if i["id"] in animal_image_ids]
        animal_cats = [c for c in full["categories"] if c["id"] in animal_cat_ids]

        filtered = {
            "info": full.get("info", {}),
            "licenses": full.get("licenses", []),
            "categories": animal_cats,
            "images": animal_images,
            "annotations": animal_anns,
        }
        with ann_out.open("w") as f:
            json.dump(filtered, f)
        logger.info(
            "saved filtered annotations: %d images, %d annotations -> %s",
            len(animal_images),
            len(animal_anns),
            ann_out,
        )

    # --- Step 2: download images ---------------------------------------------
    image_records = filtered["images"]
    total = len(image_records)
    logger.info("downloading %d animal images to %s", total, images_dir)
    for idx, record in enumerate(image_records, start=1):
        dest = images_dir / record["file_name"]
        if dest.exists():
            continue
        url = COCO_IMAGE_URL_TEMPLATE.format(file_name=record["file_name"])
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310
        except Exception as exc:  # pragma: no cover
            logger.warning("failed to download %s: %s", url, exc)
            continue
        if idx % 500 == 0 or idx == total:
            logger.info("  %d / %d images downloaded", idx, total)

    return images_dir, ann_out


def fetch_data(source: str = DEFAULT_DATA_SOURCE) -> Path:
    """Resolve a data location and return its :class:`~pathlib.Path`.

    Parameters
    ----------
    source:
        A local filesystem path to a data directory. For the local source the
        path must already exist on disk.

    Returns
    -------
    Path
        The resolved, existing data path.

    Raises
    ------
    FileNotFoundError
        If ``source`` resolves to a path that does not exist.
    ValueError
        If ``source`` uses an unsupported (non-local) scheme such as
        ``http://`` or ``s3://``.
    """
    # Reject URI-style schemes; only plain local paths are supported for now.
    if "://" in source:
        scheme = source.split("://", 1)[0]
        raise ValueError(f"unsupported data source scheme: {scheme!r}")

    path = Path(source).resolve()
    if not path.exists():
        raise FileNotFoundError(f"data source path does not exist: {path}")
    logger.info("resolved local data source: %s", path)
    return path


@hydra.main(version_base=None, config_path="../../../conf", config_name="config")
def main(cfg: DictConfig) -> None:
    """Hydra entrypoint for the fetch DVC stage."""
    source = cfg.data.source
    root = cfg.data.root
    if source == "coco":
        fetch_coco(root)
    else:
        fetch_data(root)


if __name__ == "__main__":
    # Schemas must be registered before Hydra composes the config.
    from feral_segmentor.config.store import register_configs

    register_configs()
    main()
