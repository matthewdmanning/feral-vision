"""Tests for segmentation metrics (mean_iou / dice_score)."""

from __future__ import annotations

import pytest
import torch

from feral_vision.training.metrics import dice_score, mean_iou


def test_perfect_match_is_one():
    target = torch.tensor([[[0, 0, 1, 1], [0, 0, 1, 1]]], dtype=torch.long)
    assert mean_iou(target, target) == pytest.approx(1.0)
    assert dice_score(target, target) == pytest.approx(1.0)


def test_known_partial_overlap_two_classes():
    # 2x2: target two class-0, two class-1. Prediction flips one class-1 to 0.
    #   target = [[0, 0],
    #             [1, 1]]
    #   pred   = [[0, 0],
    #             [0, 1]]
    # Class 0: intersection=2, union=3 -> IoU 2/3 ; dice 2*2/(3+2)=4/5
    # Class 1: intersection=1, union=2 -> IoU 1/2 ; dice 2*1/(1+2)=2/3
    target = torch.tensor([[[0, 0], [1, 1]]], dtype=torch.long)
    pred = torch.tensor([[[0, 0], [0, 1]]], dtype=torch.long)

    expected_iou = ((2 / 3) + (1 / 2)) / 2
    expected_dice = ((4 / 5) + (2 / 3)) / 2
    assert mean_iou(pred, target) == pytest.approx(expected_iou)
    assert dice_score(pred, target) == pytest.approx(expected_dice)


def test_disjoint_prediction_is_low():
    # All pixels class 0 in target, all class 1 in pred -> zero overlap.
    target = torch.zeros(1, 4, 4, dtype=torch.long)
    pred = torch.ones(1, 4, 4, dtype=torch.long)
    assert mean_iou(pred, target) == pytest.approx(0.0)
    assert dice_score(pred, target) == pytest.approx(0.0)


def test_logits_input_is_argmaxed():
    # logits (B, C, H, W) should be reduced via argmax over channel dim and match
    # the equivalent class-index prediction.
    target = torch.tensor([[[0, 1], [1, 0]]], dtype=torch.long)
    logits = torch.zeros(1, 2, 2, 2)
    # Make argmax over channel == target everywhere (perfect prediction).
    logits[0, 0, 0, 0] = 5.0
    logits[0, 1, 0, 1] = 5.0
    logits[0, 1, 1, 0] = 5.0
    logits[0, 0, 1, 1] = 5.0
    assert mean_iou(logits, target) == pytest.approx(1.0)
    assert dice_score(logits, target) == pytest.approx(1.0)


def test_absent_class_excluded_from_mean():
    # num_classes=3 but class 2 appears nowhere; it must not drag the mean down.
    target = torch.tensor([[[0, 1]]], dtype=torch.long)
    pred = torch.tensor([[[0, 1]]], dtype=torch.long)
    assert mean_iou(pred, target, num_classes=3) == pytest.approx(1.0)
    assert dice_score(pred, target, num_classes=3) == pytest.approx(1.0)


def test_shape_mismatch_raises():
    pred = torch.zeros(1, 2, 2, dtype=torch.long)
    target = torch.zeros(1, 3, 3, dtype=torch.long)
    with pytest.raises(ValueError):
        mean_iou(pred, target)
