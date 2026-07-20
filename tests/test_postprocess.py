"""Contracts for converting model masks into clean foreground boxes."""

from __future__ import annotations

# third-party
import pytest
import torch

# project
from feral_vision.inference.postprocess import clean_mask, masks_to_boxes


# ---------------------------------------------------------------------------
# clean_mask — binary morphology contract
# ---------------------------------------------------------------------------


def test_clean_mask_removes_isolated_specks_without_eroding_large_components():
    mask = torch.zeros((9, 9), dtype=torch.int64)
    mask[2:7, 2:7] = 1
    mask[0, 0] = 1

    cleaned = clean_mask(mask)

    assert cleaned.dtype == torch.bool
    assert not cleaned[0, 0]
    assert cleaned[2:7, 2:7].all()


@pytest.mark.parametrize("shape", [(1, 4, 4), (4,), (1, 1, 4, 4)])
def test_clean_mask_rejects_non_spatial_masks(shape):
    with pytest.raises(ValueError, match="expected a 2D"):
        clean_mask(torch.zeros(shape))


# ---------------------------------------------------------------------------
# masks_to_boxes — component-to-geometry contract
# ---------------------------------------------------------------------------


def test_masks_to_boxes_returns_exclusive_xyxy_for_each_connected_component():
    mask = torch.zeros((8, 9), dtype=torch.bool)
    mask[1:3, 2:5] = True
    mask[5:8, 6:8] = True

    boxes = masks_to_boxes(mask)

    assert boxes.dtype == torch.float32
    assert boxes.shape == (2, 4)
    assert torch.equal(
        boxes,
        torch.tensor([[2.0, 1.0, 5.0, 3.0], [6.0, 5.0, 8.0, 8.0]]),
    )


@pytest.mark.parametrize(
    "min_box_area,expected",
    [
        (1, [[0.0, 0.0, 1.0, 1.0], [3.0, 2.0, 6.0, 4.0]]),
        (2, [[3.0, 2.0, 6.0, 4.0]]),
        (7, []),
    ],
)
def test_masks_to_boxes_filters_components_by_inclusive_pixel_area(
    min_box_area, expected
):
    mask = torch.zeros((5, 7), dtype=torch.bool)
    mask[0, 0] = True
    mask[2:4, 3:6] = True

    boxes = masks_to_boxes(mask, min_box_area=min_box_area)

    assert boxes.tolist() == expected
    assert boxes.shape == (len(expected), 4)


def test_masks_to_boxes_returns_empty_float_coordinate_tensor_for_empty_mask():
    boxes = masks_to_boxes(torch.zeros((4, 6), dtype=torch.bool))

    assert boxes.shape == (0, 4)
    assert boxes.dtype == torch.float32
