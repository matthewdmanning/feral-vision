"""Contracts for supplied models and prepared CV batches; no model or data retrieval."""

from unittest.mock import create_autospec

import pytest
import torch
from torch import nn
from torchvision.models.detection import FasterRCNN, MaskRCNN

from sightkit_learn.training.execution import model_loss, prediction_loss
from sightkit_learn.training.batching import collate_huggingface, collate_vision


@pytest.mark.parametrize("task", ["classification", "semantic-segmentation"])
def test_external_criterion_accepts_classification_and_segmentation_logits(task):
    """Tensor logits and class-index targets use the same external criterion path."""
    layers = [nn.Conv2d(3, 2, kernel_size=1)]
    target_shape = (2, 8, 8)
    if task == "classification":
        layers.extend([nn.AdaptiveAvgPool2d(1), nn.Flatten()])
        target_shape = (2,)
    model = nn.Sequential(*layers)
    images = torch.ones(2, 3, 8, 8)
    targets = torch.zeros(target_shape, dtype=torch.long)

    total, components = prediction_loss(
        model, (images, targets), criterion=nn.CrossEntropyLoss()
    )
    total.backward()

    assert total.ndim == 0 and torch.isfinite(total)
    assert components == {}
    assert model[0].weight.grad is not None
    assert torch.count_nonzero(model[0].weight.grad)


@pytest.mark.parametrize("model_class", [FasterRCNN, MaskRCNN])
def test_native_loss_path_preserves_detection_and_instance_segmentation_terms(
    model_class,
):
    """A supplied native-loss model receives its prepared images and target dictionaries."""
    model = create_autospec(model_class, instance=True, spec_set=True)
    weights = nn.Parameter(torch.tensor([2.0, 3.0, 4.0]))
    model.parameters.return_value = iter([weights])
    terms = {
        "loss_classifier": weights[0].square(),
        "loss_box_reg": weights[1].square(),
    }
    images = [torch.ones(3, 8, 8)]
    targets = [
        {
            "boxes": torch.tensor([[1.0, 1.0, 6.0, 6.0]]),
            "labels": torch.tensor([1]),
        }
    ]
    if model_class is MaskRCNN:
        targets[0]["masks"] = torch.ones(1, 8, 8, dtype=torch.uint8)
        terms["loss_mask"] = weights[2].square()
    model.return_value = terms

    total, components = model_loss(model, (images, targets))
    total.backward()

    model.assert_called_once_with(images, targets)
    assert components is terms
    expected = [4.0, 6.0, 8.0 if model_class is MaskRCNN else 0.0]
    torch.testing.assert_close(weights.grad, torch.tensor(expected))
    assert total.item() == pytest.approx(29.0 if model_class is MaskRCNN else 13.0)


def test_vision_collation_preserves_variable_image_and_target_sizes():
    """Native detection and instance-segmentation inputs remain per-image lists."""
    samples = [
        (torch.ones(3, 8, 8), {"boxes": torch.ones(1, 4)}),
        (torch.ones(3, 12, 10), {"boxes": torch.ones(2, 4)}),
    ]

    images, targets = collate_vision(samples)

    assert [image.shape for image in images] == [(3, 8, 8), (3, 12, 10)]
    assert [target["boxes"].shape for target in targets] == [(1, 4), (2, 4)]


@pytest.mark.parametrize(
    "task",
    ["classification", "semantic_segmentation", "detection", "instance_segmentation"],
)
def test_huggingface_collation_preserves_native_target_layouts(task):
    """Fixed processor inputs stack while per-instance labels remain ragged."""
    samples = []
    for count in (1, 2):
        sample = {"pixel_values": torch.ones(3, 8, 8)}
        if task == "classification":
            sample["labels"] = torch.tensor(1)
        elif task == "semantic_segmentation":
            sample["labels"] = torch.ones(8, 8, dtype=torch.long)
        elif task == "detection":
            sample["labels"] = {
                "class_labels": torch.ones(count, dtype=torch.long),
                "boxes": torch.ones(count, 4),
            }
        else:
            sample["class_labels"] = torch.ones(count, dtype=torch.long)
            sample["mask_labels"] = torch.ones(count, 8, 8)
        samples.append(sample)

    batch = collate_huggingface(samples)

    assert batch["pixel_values"].shape == (2, 3, 8, 8)
    if task == "detection":
        assert [target["boxes"].shape[0] for target in batch["labels"]] == [1, 2]
    elif task == "instance_segmentation":
        assert [masks.shape[0] for masks in batch["mask_labels"]] == [1, 2]
    else:
        assert batch["labels"].shape == (
            (2,) if task == "classification" else (2, 8, 8)
        )
