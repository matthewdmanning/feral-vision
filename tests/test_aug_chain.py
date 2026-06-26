import pytest
import albumentations as A

from feral_segmentor.data.augmentations import _instantiate_transform


def test_short_name_returns_correct_type():
    transform = _instantiate_transform({"name": "HorizontalFlip"})
    assert isinstance(transform, A.HorizontalFlip)


def test_short_name_with_kwarg_returns_correct_type():
    transform = _instantiate_transform(
        {"name": "RandomBrightnessContrast", "brightness_limit": 0.1}
    )
    assert isinstance(transform, A.RandomBrightnessContrast)


def test_fully_qualified_name_returns_correct_type():
    transform = _instantiate_transform({"name": "albumentations.HorizontalFlip"})
    assert isinstance(transform, A.HorizontalFlip)


def test_unknown_short_name_raises_value_error():
    with pytest.raises(ValueError, match="unknown augmentation"):
        _instantiate_transform({"name": "NotARealTransform"})


def test_unknown_qualified_path_raises_value_error():
    with pytest.raises(ValueError):
        _instantiate_transform({"name": "nonexistent.module.Transform"})
