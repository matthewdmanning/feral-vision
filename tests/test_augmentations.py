"""Verify augmentation configs produce the promised image transformations."""

from __future__ import annotations

# third-party
import numpy as np
import pytest
from omegaconf import DictConfig, OmegaConf

# project
from feral_vision.data.augmentations import compose_augmentations


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _augmentation_cfg(ops: list[dict[str, object]]) -> DictConfig:
    """Build an augmentation config with the supplied operation definitions."""
    return OmegaConf.create({"name": "test", "ops": ops})


@pytest.fixture(params=[(16, 24), (31, 17)], ids=["landscape", "portrait"])
def uint8_image(request: pytest.FixtureRequest) -> np.ndarray:
    """Provide a seeded RGB image in each supported orientation."""
    height, width = request.param
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Pipeline behavior
# ---------------------------------------------------------------------------


def test_compose_augmentations_empty_pipeline_preserves_input(
    uint8_image: np.ndarray,
) -> None:
    result = compose_augmentations(_augmentation_cfg([]))(image=uint8_image)["image"]

    np.testing.assert_array_equal(result, uint8_image)


@pytest.mark.parametrize(
    ("transform_name", "axis"),
    [
        pytest.param("HorizontalFlip", 1, id="horizontal"),
        pytest.param("VerticalFlip", 0, id="vertical"),
    ],
)
def test_compose_augmentations_applies_configured_flip(
    uint8_image: np.ndarray, transform_name: str, axis: int
) -> None:
    pipeline = compose_augmentations(
        _augmentation_cfg([{"name": transform_name, "p": 1.0}])
    )

    result = pipeline(image=uint8_image)["image"]

    np.testing.assert_array_equal(result, np.flip(uint8_image, axis=axis))


@pytest.mark.parametrize(("height", "width"), [(1, 3), (3, 10), (10, 1)])
def test_compose_augmentations_forwards_resize_dimensions(
    uint8_image: np.ndarray, height: int, width: int
) -> None:
    pipeline = compose_augmentations(
        _augmentation_cfg([{"name": "Resize", "height": height, "width": width}])
    )

    result = pipeline(image=uint8_image)["image"]

    assert result.shape == (height, width, uint8_image.shape[-1])


# ---------------------------------------------------------------------------
# Configuration errors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "message"),
    [
        pytest.param("CompletelyFakeTransform", "unknown transform", id="unknown"),
        pytest.param(
            "HorizontalFlipp",
            "unknown transform.*did you mean",
            id="near-typo",
        ),
    ],
)
def test_compose_augmentations_rejects_unknown_transform_names(
    name: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        compose_augmentations(_augmentation_cfg([{"name": name}]))
