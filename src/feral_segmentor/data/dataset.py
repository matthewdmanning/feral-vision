"""Paired image/mask dataset for semantic segmentation."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import torch
from torch.utils.data import Dataset

from feral_segmentor.constants import DEFAULT_IMAGE_SIZE
from feral_segmentor.data.transforms import preprocess

# Subdirectories expected under the dataset root.
_IMAGES_DIR = "images"
_MASKS_DIR = "masks"


class SegmentationDataset(Dataset):
    """Dataset of ``(image, mask)`` pairs read from disk.

    Expects images under ``<root>/images`` and masks under ``<root>/masks`` with
    matching filename stems. Images are preprocessed into normalized CHW float
    tensors; masks are loaded single-channel, resized with nearest-neighbour
    interpolation (to preserve class ids), and returned as ``H x W`` long
    tensors.
    """

    def __init__(self, root: str, image_size: int = DEFAULT_IMAGE_SIZE) -> None:
        self.root = Path(root)
        self.image_size = image_size
        self.images_dir = self.root / _IMAGES_DIR
        self.masks_dir = self.root / _MASKS_DIR

        if not self.images_dir.is_dir():
            raise FileNotFoundError(f"images directory not found: {self.images_dir}")
        if not self.masks_dir.is_dir():
            raise FileNotFoundError(f"masks directory not found: {self.masks_dir}")

        # Index image files; require a matching mask (by stem) for each.
        masks_by_stem = {
            p.stem: p for p in sorted(self.masks_dir.iterdir()) if p.is_file()
        }
        self.samples: list[tuple[Path, Path]] = []
        for image_path in sorted(self.images_dir.iterdir()):
            if not image_path.is_file():
                continue
            mask_path = masks_by_stem.get(image_path.stem)
            if mask_path is None:
                raise FileNotFoundError(
                    f"no mask matching image stem {image_path.stem!r} in {self.masks_dir}"
                )
            self.samples.append((image_path, mask_path))

        if not self.samples:
            raise FileNotFoundError(f"no images found in {self.images_dir}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor]:
        image_path, mask_path = self.samples[index]

        image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"failed to read image: {image_path}")
        image_tensor = preprocess(image, size=self.image_size)

        mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)
        if mask is None:
            raise FileNotFoundError(f"failed to read mask: {mask_path}")
        # Nearest-neighbour keeps integer class ids intact during resize.
        mask = cv2.resize(
            mask,
            (self.image_size, self.image_size),
            interpolation=cv2.INTER_NEAREST,
        )
        mask_tensor = torch.from_numpy(mask.astype(np.int64))

        return image_tensor, mask_tensor
