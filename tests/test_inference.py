"""Tests for inference post-processing utilities."""

from __future__ import annotations

import torch

from feral_segmentor.inference.postprocess import clean_mask, masks_to_boxes


def test_masks_to_boxes_single_rectangle():
    mask = torch.zeros(32, 32, dtype=torch.bool)
    mask[5:15, 8:20] = True  # rows 5..14, cols 8..19
    boxes = masks_to_boxes(mask)
    assert boxes.shape == (1, 4)
    # xyxy: x1=8, y1=5, x2=20, y2=15.
    assert boxes[0].tolist() == [8.0, 5.0, 20.0, 15.0]


def test_masks_to_boxes_two_blobs():
    mask = torch.zeros(40, 40, dtype=torch.bool)
    mask[2:8, 2:8] = True
    mask[20:30, 25:35] = True
    boxes = masks_to_boxes(mask)
    assert boxes.shape[0] == 2


def test_masks_to_boxes_min_area_filter():
    mask = torch.zeros(20, 20, dtype=torch.bool)
    mask[1, 1] = True  # area 1
    boxes = masks_to_boxes(mask, min_box_area=2)
    assert boxes.shape[0] == 0


def test_clean_mask_runs():
    mask = torch.zeros(16, 16, dtype=torch.bool)
    mask[4:12, 4:12] = True
    cleaned = clean_mask(mask)
    assert cleaned.shape == mask.shape
    assert cleaned.dtype == torch.bool
