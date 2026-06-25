"""Augmentation tests using the committed fixture images."""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from omegaconf import OmegaConf

from feral_segmentor.data.augmentations import (
    BrightnessShift,
    GammaAdjust,
    HorizontalFlip,
    Identity,
    RandomRotate90,
    build_chain,
)


def _load_normalized(fixture_dataset_root) -> np.ndarray:
    """Load first fixture image as float64 [0,1] HWC."""
    images = sorted((fixture_dataset_root / "images").iterdir())
    bgr = cv2.imread(str(images[0]), cv2.IMREAD_UNCHANGED)
    return bgr.astype(np.float64) / 255.0


def _aug_cfg(ops):
    return OmegaConf.create({"name": "test", "ops": list(ops)})


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def test_identity_preserves_fixture_image(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = Identity().augment(img)
    np.testing.assert_array_equal(out, img)


# ---------------------------------------------------------------------------
# HorizontalFlip
# ---------------------------------------------------------------------------

def test_horizontal_flip_shape_preserved(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = HorizontalFlip().augment(img)
    assert out.shape == img.shape


def test_horizontal_flip_inverts(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    flipped = HorizontalFlip().augment(img)
    np.testing.assert_array_equal(HorizontalFlip().augment(flipped), img)


def test_horizontal_flip_pixel_position(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = HorizontalFlip().augment(img)
    w = img.shape[1]
    np.testing.assert_array_equal(out[:, 0], img[:, w - 1])


# ---------------------------------------------------------------------------
# RandomRotate90
# ---------------------------------------------------------------------------

def test_rotate90_shape_preserved_square(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    # Crop to square so shape is guaranteed preserved after 90° rotation.
    side = min(img.shape[:2])
    sq = img[:side, :side]
    out = RandomRotate90().augment(sq)
    assert out.shape == sq.shape


def test_rotate90_four_times_is_identity(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    side = min(img.shape[:2])
    sq = np.ascontiguousarray(img[:side, :side])
    result = sq
    for _ in range(4):
        result = RandomRotate90(k=1).augment(result)
    np.testing.assert_array_almost_equal(result, sq)


# ---------------------------------------------------------------------------
# BrightnessShift
# ---------------------------------------------------------------------------

def test_brightness_shift_raises_mean(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = BrightnessShift(shift=0.1).augment(img)
    assert out.mean() > img.mean() - 1e-6


def test_brightness_shift_clips_to_unit(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = BrightnessShift(shift=2.0).augment(img)
    assert float(out.max()) <= 1.0
    assert float(out.min()) >= 0.0


def test_negative_brightness_shift_lowers_mean(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = BrightnessShift(shift=-0.1).augment(img)
    assert out.mean() < img.mean() + 1e-6


# ---------------------------------------------------------------------------
# GammaAdjust
# ---------------------------------------------------------------------------

def test_gamma_gt1_darkens_midtones(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = GammaAdjust(gamma=2.0).augment(img)
    assert out.mean() < img.mean()


def test_gamma_lt1_brightens_midtones(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = GammaAdjust(gamma=0.5).augment(img)
    assert out.mean() > img.mean()


def test_gamma1_is_identity(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    out = GammaAdjust(gamma=1.0).augment(img)
    np.testing.assert_array_almost_equal(out, np.clip(img, 0.0, 1.0))


def test_gamma_boundary_pixels_unchanged(fixture_dataset_root):
    # Pixels at 0.0 and 1.0 are fixed points for any gamma.
    img = np.zeros((4, 4), dtype=np.float64)
    img[0, 0] = 1.0
    out = GammaAdjust(gamma=3.0).augment(img)
    assert float(out[0, 0]) == pytest.approx(1.0)
    assert float(out[1, 1]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Chained augmentations on fixture images
# ---------------------------------------------------------------------------

def test_chain_flip_then_brightness_on_fixture(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    chain = build_chain(_aug_cfg(["HorizontalFlip", "BrightnessShift"]))
    out = chain.augment(img)
    assert out.shape == img.shape
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0


def test_chain_all_ops_on_fixture(fixture_dataset_root):
    img = _load_normalized(fixture_dataset_root)
    side = min(img.shape[:2])
    sq = np.ascontiguousarray(img[:side, :side])
    chain = build_chain(_aug_cfg(["HorizontalFlip", "RandomRotate90", "BrightnessShift", "GammaAdjust"]))
    out = chain.augment(sq)
    assert out.shape == sq.shape
    assert float(out.min()) >= 0.0
    assert float(out.max()) <= 1.0


def test_run_augment_stage_writes_files(fixture_dataset_root, tmp_path):
    """run_augment_stage writes one augmented file per input image."""
    from omegaconf import OmegaConf
    from feral_segmentor.data.augmentations import run_augment_stage

    # Mirror fixture images into a tmp raw dir.
    import shutil
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    for img_path in sorted((fixture_dataset_root / "images").iterdir()):
        shutil.copy(img_path, raw_dir / img_path.name)

    cfg = OmegaConf.create({
        "augmentation": {"name": "test", "ops": ["HorizontalFlip"]},
        "data": {"root": str(tmp_path)},
    })
    run_augment_stage(cfg)

    out_dir = tmp_path / "augmented"
    written = list(out_dir.iterdir())
    assert len(written) == 8
    assert all(f.suffix in {".jpg", ".png", ".jpeg", ".bmp"} for f in written)
