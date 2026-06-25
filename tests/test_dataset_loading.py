"""Dataset loading tests using the committed 8-sample fixture."""

from __future__ import annotations

import numpy as np
import pytest
import torch
from torch.utils.data import DataLoader

from feral_segmentor.constants import DEFAULT_IMAGE_SIZE
from feral_segmentor.data.dataset import SegmentationDataset


# ---------------------------------------------------------------------------
# Basic loading
# ---------------------------------------------------------------------------


def test_fixture_dataset_length(fixture_dataset):
    assert len(fixture_dataset) == 8


def test_fixture_dataset_image_shape(fixture_dataset):
    img, _ = fixture_dataset[0]
    assert img.shape == (3, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


def test_fixture_dataset_image_dtype(fixture_dataset):
    img, _ = fixture_dataset[0]
    assert img.dtype == torch.float32


def test_fixture_dataset_image_range(fixture_dataset):
    img, _ = fixture_dataset[0]
    assert float(img.min()) >= 0.0
    assert float(img.max()) <= 1.0


def test_fixture_dataset_mask_shape(fixture_dataset):
    _, mask = fixture_dataset[0]
    assert mask.shape == (DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


def test_fixture_dataset_mask_dtype(fixture_dataset):
    _, mask = fixture_dataset[0]
    assert mask.dtype == torch.int64


def test_fixture_dataset_mask_binary(fixture_dataset):
    """Oxford trimaps binarized to 0/1 only."""
    for i in range(len(fixture_dataset)):
        _, mask = fixture_dataset[i]
        unique = mask.unique().tolist()
        assert set(unique).issubset({0, 1}), (
            f"sample {i} has unexpected mask values: {unique}"
        )


# ---------------------------------------------------------------------------
# All samples loadable
# ---------------------------------------------------------------------------


def test_fixture_dataset_all_samples_load(fixture_dataset):
    for i in range(len(fixture_dataset)):
        img, mask = fixture_dataset[i]
        assert img.shape == (3, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)
        assert mask.shape == (DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


# ---------------------------------------------------------------------------
# DataLoader integration
# ---------------------------------------------------------------------------


def test_fixture_dataset_dataloader_batch(fixture_dataset):
    loader = DataLoader(fixture_dataset, batch_size=4, shuffle=False)
    imgs, masks = next(iter(loader))
    assert imgs.shape == (4, 3, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)
    assert masks.shape == (4, DEFAULT_IMAGE_SIZE, DEFAULT_IMAGE_SIZE)


def test_fixture_dataset_dataloader_full_pass(fixture_dataset):
    loader = DataLoader(fixture_dataset, batch_size=2, shuffle=False)
    total = sum(imgs.shape[0] for imgs, _ in loader)
    assert total == 8


def test_fixture_dataset_dataloader_shuffle_same_count(fixture_dataset):
    loader = DataLoader(fixture_dataset, batch_size=8, shuffle=True)
    imgs, masks = next(iter(loader))
    assert imgs.shape[0] == 8


# ---------------------------------------------------------------------------
# Custom image_size
# ---------------------------------------------------------------------------


def test_fixture_dataset_custom_size(fixture_dataset_root):
    ds = SegmentationDataset(str(fixture_dataset_root), image_size=128)
    img, mask = ds[0]
    assert img.shape == (3, 128, 128)
    assert mask.shape == (128, 128)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_dataset_missing_root_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SegmentationDataset(str(tmp_path / "nonexistent"))


def test_dataset_missing_masks_dir_raises(tmp_path):
    (tmp_path / "images").mkdir()
    with pytest.raises(FileNotFoundError):
        SegmentationDataset(str(tmp_path))


def test_dataset_missing_images_dir_raises(tmp_path):
    (tmp_path / "masks").mkdir()
    with pytest.raises(FileNotFoundError):
        SegmentationDataset(str(tmp_path))


def test_dataset_unmatched_image_raises(tmp_path):
    import cv2

    (tmp_path / "images").mkdir()
    (tmp_path / "masks").mkdir()
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "images" / "sample.png"), img)
    # No matching mask -> should raise
    with pytest.raises(FileNotFoundError):
        SegmentationDataset(str(tmp_path))


def test_dataset_empty_images_dir_raises(tmp_path):
    (tmp_path / "images").mkdir()
    (tmp_path / "masks").mkdir()
    with pytest.raises(FileNotFoundError):
        SegmentationDataset(str(tmp_path))
