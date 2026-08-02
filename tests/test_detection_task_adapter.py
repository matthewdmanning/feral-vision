"""Detection task batches preserve YOLO labels and delegate native assignment safely."""

from __future__ import annotations

# stdlib
from pathlib import Path

# third-party
import pytest
import torch
from torch import nn

# project
from feral_vision.data.annotations import BBoxAnnotation
from feral_vision.training.task_adapters.detection import DetectionTaskAdapter


# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


def _annotation(class_ids: list[int], boxes: list[list[float]]) -> BBoxAnnotation:
    """Build an in-memory YOLO annotation for a two-dimensional image sample."""
    return BBoxAnnotation(
        path=Path("sample.txt"),
        class_ids=torch.tensor(class_ids).numpy(),
        boxes=torch.tensor(boxes, dtype=torch.float32).numpy(),
    )


class _NativeCriterion:
    """Minimal native-assignment facade exposing the detector criterion contract."""

    def parse_output(self, predictions):
        """Return the prediction mapping supplied by the lightweight test detector."""
        return predictions

    def get_assigned_targets_and_loss(self, predictions, batch):
        """Return one native foreground match and a differentiable classification component."""
        foreground = torch.tensor([[True, False]], device=batch["img"].device)
        target_boxes = torch.tensor(
            [[[0.0, 0.0, 2.0, 2.0], [0.0, 0.0, 0.0, 0.0]]],
            device=batch["img"].device,
        )
        anchor_points = torch.zeros((2, 2), device=batch["img"].device)
        stride = torch.ones((2, 1), device=batch["img"].device)
        classification = predictions["scores"].sum() * 0.0 + 2.0
        return (
            (
                foreground,
                torch.zeros_like(foreground),
                target_boxes,
                anchor_points,
                stride,
            ),
            torch.stack((classification * 0.0, classification, classification * 0.0)),
            torch.zeros(3, device=batch["img"].device),
        )

    def bbox_decode(self, anchor_points, predicted_distances):
        """Treat the first four detector values as already-decoded xyxy boxes."""
        return predicted_distances[..., :4]


class _NativeDetector(nn.Module):
    """Tiny two-dimensional detector exposing an Ultralytics-like native criterion initializer."""

    def __init__(self) -> None:
        super().__init__()
        self.score = nn.Parameter(torch.tensor(1.0))

    def forward(self, images):
        """Emit two box candidates and one differentiable classification score per image."""
        batch_size = images.shape[0]
        boxes = torch.tensor(
            [[[0.0, 0.0], [0.0, 0.0], [2.0, 1.0], [2.0, 1.0]]],
            dtype=images.dtype,
            device=images.device,
        ).expand(batch_size, -1, -1)
        return {"boxes": boxes, "scores": self.score.view(1, 1, 1)}

    def init_criterion(self):
        """Create the native-assignment criterion expected by the task adapter."""
        return _NativeCriterion()


# ---------------------------------------------------------------------------
# DetectionTaskAdapter — batch and loss contracts
# ---------------------------------------------------------------------------


def test_collate_keeps_variable_box_counts_and_normalized_images() -> None:
    """One detection batch retains every class-labelled box without padding targets."""
    adapter = DetectionTaskAdapter(num_classes=10)

    batch = adapter.collate(
        [
            (
                torch.zeros(3, 8, 8, dtype=torch.uint8),
                [_annotation([1], [[0.5, 0.5, 0.4, 0.4]])],
            ),
            (
                torch.full((3, 8, 8), 255, dtype=torch.uint8),
                [_annotation([2, 3], [[0.2, 0.2, 0.1, 0.1], [0.8, 0.8, 0.1, 0.1]])],
            ),
        ]
    )

    assert batch.images.shape == (2, 3, 8, 8)
    assert batch.batch_idx.tolist() == [0, 1, 1]
    assert batch.class_ids.tolist() == [1, 2, 3]
    assert batch.boxes.shape == (3, 4)


def test_collate_rejects_class_ids_outside_the_selected_taxonomy() -> None:
    """The two-class recipe contract rejects label drift before native assignment."""
    adapter = DetectionTaskAdapter(num_classes=2)

    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        adapter.collate(
            [
                (
                    torch.zeros(3, 8, 8, dtype=torch.uint8),
                    [_annotation([2], [[0.5, 0.5, 0.4, 0.4]])],
                )
            ]
        )


def test_loss_reuses_native_assignment_and_replaces_box_component_with_giou() -> None:
    """The adapter combines native classification with GIoU for one matching box."""
    adapter = DetectionTaskAdapter(num_classes=10)
    model = _NativeDetector()
    batch = adapter.collate(
        [
            (
                torch.full((3, 8, 8), 255, dtype=torch.uint8),
                [_annotation([1], [[0.5, 0.5, 0.4, 0.4]])],
            )
        ]
    )

    loss, metrics = adapter.loss(model, batch)
    loss.backward()

    assert loss.item() == pytest.approx(2.0)
    assert metrics == {"classification_loss": 2.0, "giou_loss": 0.0}
    assert model.score.grad is not None
