import numpy as np
import pytest
import albumentations as A
from omegaconf import OmegaConf

from feral_vision.data.augmentations import compose_augmentations


def _aug_cfg(ops):
    return OmegaConf.create({"name": "test", "ops": ops})


def _uint8_image():
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)


def test_empty_ops_returns_compose():
    pipeline = compose_augmentations(_aug_cfg([]))
    assert isinstance(pipeline, A.Compose)


def test_empty_ops_passes_image_unchanged():
    pipeline = compose_augmentations(_aug_cfg([]))
    image = _uint8_image()
    result = pipeline(image=image)["image"]
    np.testing.assert_array_equal(result, image)


def test_known_short_name_preserves_shape():
    ops = [{"name": "HorizontalFlip", "p": 1.0}]
    pipeline = compose_augmentations(_aug_cfg(ops))
    image = _uint8_image()
    result = pipeline(image=image)["image"]
    assert result.shape == image.shape


def test_unknown_name_raises_value_error():
    ops = [{"name": "CompletelyFakeTransform"}]
    with pytest.raises(ValueError, match="unknown transform"):
        compose_augmentations(_aug_cfg(ops))


def test_near_typo_name_suggests_did_you_mean():
    ops = [{"name": "HorizontalFlipp"}]
    with pytest.raises(ValueError, match="did you mean"):
        compose_augmentations(_aug_cfg(ops))
