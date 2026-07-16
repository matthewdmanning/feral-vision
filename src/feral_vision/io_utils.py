from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import torch
from torchvision.io import read_image

from feral_vision.data.annotations import (
    Annotation,
    BBoxAnnotation,
    MaskAnnotation,
)

_IMAGES_DIR = "images"
_ANNOTATIONS_DIR = "annotations"


def load_image(path: str | Path):
    """Use this function to load an image from disk as an unchanged NumPy array (BGR, any depth).

    Parameters
    ----------
    path : str or Path
        Path to the image file.

    Returns
    -------
    numpy.ndarray
        Image array as read by OpenCV (BGR channel order, native bit depth).
    """
    import cv2

    return cv2.imread(str(path), cv2.IMREAD_UNCHANGED)


def save_image(image, path: str | Path) -> None:
    """Use this function to write a NumPy image array to disk.

    Parameters
    ----------
    image : numpy.ndarray
        Image array in BGR channel order.
    path : str or Path
        Destination file path. Extension determines the format.
    """
    import cv2

    cv2.imwrite(str(path), image)


def read_json(path: str | Path) -> Any:
    """Use this function to load a JSON file and return its contents as a Python object.

    Parameters
    ----------
    path : str or Path
        Path to the JSON file.

    Returns
    -------
    Any
        Parsed JSON content.
    """
    return json.loads(Path(path).read_text())


def write_json(data: Any, path: str | Path) -> None:
    """Use this function to serialise a Python object to a pretty-printed JSON file.

    Parameters
    ----------
    data : Any
        JSON-serialisable object.
    path : str or Path
        Destination file path.
    """
    Path(path).write_text(json.dumps(data, indent=2))


def _build_index(root: Path) -> list[tuple[Path, list[Path]]]:
    """Use this function to scan a dataset root and pair each image with its annotation file(s).

    Scans ``root/images/`` and ``root/annotations/`` by filename stem.
    ``names.yaml`` is excluded from annotation matching.

    Parameters
    ----------
    root : Path
        Root directory containing ``images/`` and ``annotations/``
        subdirectories.

    Returns
    -------
    list[tuple[Path, list[Path]]]
        Sorted list of ``(image_path, [annotation_paths])`` pairs.

    Raises
    ------
    FileNotFoundError
        If any image has no matching annotation by stem.
    """
    images_dir = root / _IMAGES_DIR
    annotations_dir = root / _ANNOTATIONS_DIR

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

    return samples


def _read_image_tensor(path: Path) -> torch.Tensor:
    """Use this function to load an image as a ``(C, H, W)`` uint8 tensor for use in PyTorch datasets.

    Parameters
    ----------
    path : Path
        Path to the image file.

    Returns
    -------
    torch.Tensor
        Image tensor of shape ``(C, H, W)`` with dtype ``uint8``.
    """
    return read_image(str(path))


def _load_annotation(path: Path) -> Annotation:
    """Use this function to load an annotation file, dispatching to the correct type by extension.

    Parameters
    ----------
    path : Path
        Path to the annotation file. Extension determines the annotation type:
        ``.png``/``.jpg``/``.bmp`` → :class:`~feral_vision.data.annotations.MaskAnnotation`;
        ``.txt`` → :class:`~feral_vision.data.annotations.BBoxAnnotation`.

    Returns
    -------
    Annotation
        A fully loaded annotation object.

    Raises
    ------
    NotImplementedError
        If the file extension has no registered annotation loader.
    """
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".bmp"}:
        return MaskAnnotation(path=path).load()
    if suffix == ".txt":
        return BBoxAnnotation(path=path).load()
    raise NotImplementedError(f"no annotation loader for {suffix!r}: {path}")


class DatasetSource:
    """Scans a root directory and loads image / annotation pairs on demand.

    Owns all filesystem scanning and disk I/O. Inject into
    :class:`~feral_vision.data.dataset.AnnotationDataset` or
    :class:`~feral_vision.data.dataset.StreamingAnnotationDataset`.

    Parameters
    ----------
    root : str or Path
        Root directory containing ``images/`` and ``annotations/``
        subdirectories.
    """

    def __init__(self, root: str | Path) -> None:
        self._index = _build_index(Path(root))

    def __len__(self) -> int:
        """Return the total number of image / annotation pairs."""
        return len(self._index)

    def load(self, index: int) -> tuple[torch.Tensor, list[Annotation]]:
        """Load and return one image / annotation pair.

        Parameters
        ----------
        index : int
            Sample index.

        Returns
        -------
        tuple[torch.Tensor, list[Annotation]]
            ``(image, annotations)`` where image is ``(C, H, W)`` uint8.
        """
        img_path, ann_paths = self._index[index]
        return _read_image_tensor(img_path), [_load_annotation(p) for p in ann_paths]

    def partition(self, worker_id: int, num_workers: int) -> DatasetSource:
        """Return a view covering only this worker's contiguous slice of the index.

        Parameters
        ----------
        worker_id : int
            Zero-based worker index.
        num_workers : int
            Total number of workers.

        Returns
        -------
        DatasetSource
            A shallow copy whose ``_index`` covers only this worker's slice.
        """
        per_worker = math.ceil(len(self._index) / num_workers)
        start = worker_id * per_worker
        sliced: DatasetSource = object.__new__(DatasetSource)
        sliced._index = self._index[start : start + per_worker]
        return sliced
