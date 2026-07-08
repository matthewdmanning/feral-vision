"""Paired image / annotation dataset."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Iterator

from PIL import Image
from torch.utils.data import Dataset, IterableDataset, get_worker_info

from feral_segmentor.data.annotations import Annotation, BBoxAnnotation, MaskAnnotation

_IMAGES_DIR = "images"
_ANNOTATIONS_DIR = "annotations"


def _load_image(path: Path) -> Image.Image:
    return Image.open(path)


def _load_annotation(path: Path) -> Annotation:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp"}:
        return MaskAnnotation(path=path).load()
    if suffix == ".txt":
        return BBoxAnnotation(path=path).load()
    raise NotImplementedError(f"no annotation loader for {suffix!r}: {path}")


def _load_sample(
    img_path: Path, ann_paths: list[Path]
) -> tuple[Image.Image, list[Annotation]]:
    return _load_image(img_path), [_load_annotation(p) for p in ann_paths]


def _build_index(root: Path) -> list[tuple[Path, list[Path]]]:
    images_dir = root / _IMAGES_DIR
    annotations_dir = root / _ANNOTATIONS_DIR

    if not images_dir.is_dir():
        raise FileNotFoundError(f"images directory not found: {images_dir}")
    if not annotations_dir.is_dir():
        raise FileNotFoundError(f"annotations directory not found: {annotations_dir}")

    annotations_by_stem: dict[str, list[Path]] = {}
    for p in sorted(annotations_dir.iterdir()):
        if p.is_file() and p.stem != "names":
            annotations_by_stem.setdefault(p.stem, []).append(p)

    samples: list[tuple[Path, list[Path]]] = []
    for image_path in sorted(images_dir.iterdir()):
        if not image_path.is_file():
            continue
        ann_paths = annotations_by_stem.get(image_path.stem)
        if ann_paths is None:
            raise FileNotFoundError(
                f"no annotation matching image stem {image_path.stem!r}"
                f" in {annotations_dir}"
            )
        samples.append((image_path, ann_paths))

    if not samples:
        raise FileNotFoundError(f"no images found in {images_dir}")

    return samples


class AnnotationDataset(Dataset[tuple[Image.Image, list[Annotation]]]):
    """Map-style dataset for on-disk image / annotation pairs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.samples = _build_index(self.root)

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[Image.Image, list[Annotation]]:
        img_path, ann_paths = self.samples[index]
        return _load_sample(img_path, ann_paths)


class StreamingAnnotationDataset(IterableDataset[tuple[Image.Image, list[Annotation]]]):
    """Iterable dataset for streaming image / annotation pairs."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.samples = _build_index(self.root)

    def __iter__(self) -> Iterator[tuple[Image.Image, list[Annotation]]]:
        worker_info = get_worker_info()
        if worker_info is None:
            samples = self.samples
        else:
            per_worker = math.ceil(len(self.samples) / worker_info.num_workers)
            start = worker_info.id * per_worker
            samples = self.samples[start : start + per_worker]
        for img_path, ann_paths in samples:
            yield _load_sample(img_path, ann_paths)
