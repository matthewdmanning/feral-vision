"""Detection batch translation and native-assignment custom loss support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import torch
from torch import nn
from torchvision.ops import generalized_box_iou_loss

from feral_vision.data.annotations import BBoxAnnotation


@dataclass(frozen=True)
class DetectionBatch:
    """Represents a collated detection batch ready for an Ultralytics PyTorch module."""

    images: torch.Tensor
    batch_idx: torch.Tensor
    class_ids: torch.Tensor
    boxes: torch.Tensor


class DetectionTaskAdapter:
    """Translates YOLO annotations into native-assigned classification and GIoU training losses."""

    def __init__(self, *, num_classes: int) -> None:
        self.num_classes = num_classes

    def collate(
        self, samples: Iterable[tuple[torch.Tensor, list[Any]]]
    ) -> DetectionBatch:
        """Use this function when a DataLoader must retain variable YOLO boxes per image."""
        images: list[torch.Tensor] = []
        batch_indices: list[torch.Tensor] = []
        class_ids: list[torch.Tensor] = []
        boxes: list[torch.Tensor] = []

        for index, (image, sample_annotations) in enumerate(samples):
            annotation = _bbox_annotation(sample_annotations)
            images.append(image)
            if annotation.boxes is None or annotation.class_ids is None:
                annotation.load()
            assert annotation.boxes is not None and annotation.class_ids is not None
            if len(annotation.boxes) != len(annotation.class_ids):
                raise ValueError("detection boxes and class IDs must have equal length")
            if len(annotation.class_ids) and (
                annotation.class_ids.min() < 0
                or annotation.class_ids.max() >= self.num_classes
            ):
                raise ValueError(
                    f"detection class IDs must be in [0, {self.num_classes - 1}]"
                )
            count = len(annotation.boxes)
            if count:
                batch_indices.append(torch.full((count,), index, dtype=torch.long))
                class_ids.append(
                    torch.as_tensor(annotation.class_ids, dtype=torch.long)
                )
                boxes.append(torch.as_tensor(annotation.boxes, dtype=torch.float32))

        if not images:
            raise ValueError("detection batch must contain at least one image")
        return DetectionBatch(
            images=torch.stack(images),
            batch_idx=torch.cat(batch_indices)
            if batch_indices
            else torch.empty(0, dtype=torch.long),
            class_ids=torch.cat(class_ids)
            if class_ids
            else torch.empty(0, dtype=torch.long),
            boxes=torch.cat(boxes)
            if boxes
            else torch.empty((0, 4), dtype=torch.float32),
        )

    def loss(
        self, model: nn.Module, batch: DetectionBatch
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """Use this function to train a native-assignment detector with classification plus GIoU loss."""
        device = next(model.parameters()).device
        images = batch.images.to(device).float()
        if batch.images.dtype == torch.uint8:
            images = images / 255.0
        native_batch = {
            "img": images,
            "batch_idx": batch.batch_idx.to(images.device),
            "cls": batch.class_ids.to(images.device).view(-1, 1),
            "bboxes": batch.boxes.to(images.device),
        }
        predictions = model(images)
        criterion = _native_detection_criterion(model)
        parsed_predictions = criterion.parse_output(predictions)
        assignment, native_components, _ = criterion.get_assigned_targets_and_loss(
            parsed_predictions, native_batch
        )
        foreground, _, target_boxes, anchor_points, stride = assignment
        predicted_distances = parsed_predictions["boxes"].permute(0, 2, 1).contiguous()
        predicted_boxes = (
            criterion.bbox_decode(anchor_points, predicted_distances) * stride
        )
        if foreground.any():
            giou = (
                generalized_box_iou_loss(
                    predicted_boxes[foreground],
                    target_boxes[foreground],
                    reduction="sum",
                )
                / foreground.sum()
            )
        else:
            giou = predicted_boxes.sum() * 0.0
        classification = native_components[1]
        loss = (classification + giou) * images.shape[0]
        return loss, {
            "classification_loss": float(classification.detach()),
            "giou_loss": float(giou.detach()),
        }


def _bbox_annotation(annotations: list[Any]) -> BBoxAnnotation:
    """Use this function when a detection sample must expose exactly one YOLO box annotation."""
    matches = [
        annotation
        for annotation in annotations
        if isinstance(annotation, BBoxAnnotation)
    ]
    if len(matches) != 1:
        raise ValueError("detection samples require exactly one BBoxAnnotation")
    return matches[0]


def _native_detection_criterion(model: nn.Module) -> Any:
    """Use this function when an Ultralytics module needs its native target assigner initialized."""
    criterion = getattr(model, "criterion", None)
    if criterion is None:
        initializer = getattr(model, "init_criterion", None)
        if initializer is None:
            raise TypeError(
                "detection model must provide init_criterion() for native assignment"
            )
        criterion = initializer()
        setattr(model, "criterion", criterion)
    required_methods = ("parse_output", "get_assigned_targets_and_loss", "bbox_decode")
    if not all(hasattr(criterion, method) for method in required_methods):
        raise TypeError(
            "detection model criterion does not expose native assignment APIs"
        )
    return criterion
