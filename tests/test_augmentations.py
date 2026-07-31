"""Verify augmentation configs produce the promised image transformations."""

from __future__ import annotations

# third-party
import numpy as np
import pytest

# project
from feral_vision.data.augmentations import (
    AugmentationSweep,
    _instantiate_transform,
    build_augmentation_previews,
    write_augmentation_preview_html,
)

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _pipeline(ops: list[dict[str, object]]):
    """Build a direct Albumentations pipeline from configured transform mappings."""
    import albumentations as A

    return A.Compose([_instantiate_transform(op) for op in ops])


@pytest.fixture(params=[(16, 24), (31, 17)], ids=["landscape", "portrait"])
def uint8_image(request: pytest.FixtureRequest) -> np.ndarray:
    """Provide a seeded RGB image in each supported orientation."""
    height, width = request.param
    rng = np.random.default_rng(0)
    return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)


# ---------------------------------------------------------------------------
# Pipeline behavior
# ---------------------------------------------------------------------------


def test_direct_albumentations_pipeline_empty_config_preserves_input(
    uint8_image: np.ndarray,
) -> None:
    result = _pipeline([])(image=uint8_image)["image"]

    np.testing.assert_array_equal(result, uint8_image)


@pytest.mark.parametrize(
    ("transform_name", "axis"),
    [
        pytest.param("HorizontalFlip", 1, id="horizontal"),
        pytest.param("VerticalFlip", 0, id="vertical"),
    ],
)
def test_direct_albumentations_pipeline_applies_configured_flip(
    uint8_image: np.ndarray, transform_name: str, axis: int
) -> None:
    pipeline = _pipeline([{"name": transform_name, "p": 1.0}])

    result = pipeline(image=uint8_image)["image"]

    np.testing.assert_array_equal(result, np.flip(uint8_image, axis=axis))


@pytest.mark.parametrize(("height", "width"), [(1, 3), (3, 10), (10, 1)])
def test_direct_albumentations_pipeline_forwards_resize_dimensions(
    uint8_image: np.ndarray, height: int, width: int
) -> None:
    pipeline = _pipeline([{"name": "Resize", "height": height, "width": width}])

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
def test_transform_construction_rejects_unknown_transform_names(
    name: str, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _pipeline([{"name": name}])


def test_build_augmentation_previews_returns_all_source_pages_as_grids(
    tmp_path,
) -> None:
    """Use this test to protect the local human-review preview contract."""
    import cv2

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_image = np.arange(36, dtype=np.uint8).reshape(3, 4, 3)
    assert cv2.imwrite(str(source_dir / "one.png"), source_image)
    assert cv2.imwrite(str(source_dir / "two.png"), source_image + 1)

    previews = build_augmentation_previews(
        source_dir,
        [
            {"name": "HorizontalFlip", "p": 1.0},
            {"name": "VerticalFlip", "p": 1.0},
        ],
        [
            AugmentationSweep("HorizontalFlip", "p", (0.0, 1.0), is_binary=True),
            AugmentationSweep("VerticalFlip", "p", (0.0, 1.0), is_binary=True),
        ],
    )

    assert len(previews) == 2
    assert previews[0].source_path.name == "one.png"
    assert previews[0].row_sweep.transform == "HorizontalFlip"
    assert previews[0].column_sweep.transform == "VerticalFlip"
    assert [[variant.settings for variant in row] for row in previews[0].variants] == [
        [
            {"HorizontalFlip.p": 0.0, "VerticalFlip.p": 0.0},
            {"HorizontalFlip.p": 0.0, "VerticalFlip.p": 1.0},
        ],
        [
            {"HorizontalFlip.p": 1.0, "VerticalFlip.p": 0.0},
            {"HorizontalFlip.p": 1.0, "VerticalFlip.p": 1.0},
        ],
    ]
    np.testing.assert_array_equal(previews[0].variants[0][0].image, source_image)
    np.testing.assert_array_equal(
        previews[0].variants[-1][-1].image, np.flip(source_image, axis=(0, 1))
    )


def test_build_augmentation_previews_rejects_duplicate_sweeps(tmp_path) -> None:
    """Use this test to preserve distinct preview dimensions for every sweep."""
    import cv2

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    assert cv2.imwrite(str(source_dir / "one.png"), np.zeros((3, 4, 3), dtype=np.uint8))

    with pytest.raises(ValueError, match="duplicate sweep HorizontalFlip.p"):
        build_augmentation_previews(
            source_dir,
            [{"name": "HorizontalFlip", "p": 1.0}],
            [
                AugmentationSweep("HorizontalFlip", "p", (0.0, 1.0), is_binary=True),
                AugmentationSweep("HorizontalFlip", "p", (0.0, 1.0), is_binary=True),
            ],
        )


def test_build_augmentation_previews_requires_three_non_binary_values(tmp_path) -> None:
    """Use this test to preserve enough variation for human augmentation review."""
    import cv2

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    assert cv2.imwrite(str(source_dir / "one.png"), np.zeros((3, 4, 3), dtype=np.uint8))

    with pytest.raises(ValueError, match="Rotate.limit requires at least three values"):
        build_augmentation_previews(
            source_dir,
            [
                {"name": "Rotate", "limit": 0, "p": 1.0},
                {"name": "VerticalFlip", "p": 1.0},
            ],
            [
                AugmentationSweep("Rotate", "limit", (-10, 10)),
                AugmentationSweep("VerticalFlip", "p", (0.0, 1.0), is_binary=True),
            ],
        )


def test_write_augmentation_preview_html_creates_structured_grid_assets(
    tmp_path,
) -> None:
    """Use this test to protect the interactive local augmentation-viewer contract."""
    import cv2

    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_image = np.arange(36, dtype=np.uint8).reshape(3, 4, 3)
    assert cv2.imwrite(str(source_dir / "one.png"), source_image)
    previews = build_augmentation_previews(
        source_dir,
        [
            {"name": "HorizontalFlip", "p": 1.0},
            {"name": "VerticalFlip", "p": 1.0},
        ],
        [
            AugmentationSweep(
                "HorizontalFlip",
                "p",
                (0.0, 0.5, 1.0),
                display_values=("off", "partial", "full"),
            ),
            AugmentationSweep("VerticalFlip", "p", (0.0, 0.5, 1.0)),
        ],
    )

    index = write_augmentation_preview_html(previews, tmp_path / "aug_preview")

    document = index.read_text(encoding="utf-8")
    assert index.name == "index.html"
    assert 'type="range"' in document
    assert 'data-action="decrease"' in document
    assert 'class="workspace"' in document
    assert 'class="controls"' in document
    assert "grid-template-columns: repeat(2, minmax(19rem, 1fr))" in document
    assert 'class="slider-pair"' in document
    assert 'class="slider-row"' in document
    assert "pointer-events: none" not in document
    assert 'className: "original-badge", textContent: "Original source"' in document
    assert (
        "image.src = isOriginal ? page.sourceAsset : page.variants[row][column]"
        in document
    )
    assert "object-fit: contain" in document
    assert '"displayValues": ["off", "partial", "full"]' in document
    assert len(tuple(index.parent.glob("assets/page-1/*.png"))) == 10
    rendered_source = cv2.imread(str(index.parent / "assets/page-1/source.png"))
    np.testing.assert_array_equal(rendered_source, source_image)
