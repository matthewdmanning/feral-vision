"""Loss-computation callables consumed by the shared optimizer loop."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import torch
from torch import nn

from sightkit_learn.utils import to_device

LossComputation = Callable[
    [nn.Module, Any], tuple[torch.Tensor, dict[str, torch.Tensor]]
]


def prediction_loss(
    model: nn.Module,
    batch: tuple[torch.Tensor, Any],
    *,
    criterion: Callable[[Any, Any], torch.Tensor],
    aux_weight: float = 0.5,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Compute an external criterion after a model forward pass.

    Parameters
    ----------
    model : nn.Module
        Model whose outputs the supplied criterion accepts.
    batch : tuple[Tensor, Any]
        Input tensors and targets accepted by the configured criterion, including
        soft teacher outputs or structured human annotations.
    criterion : callable
        Scalar differentiable criterion, including a composite criterion.
    aux_weight : float
        Weight for TorchVision semantic-segmentation auxiliary logits.

    Returns
    -------
    tuple[Tensor, dict[str, Tensor]]
        Total loss and optional reporting terms.
    """
    device = next(model.parameters()).device
    inputs, targets = batch
    targets = to_device(targets, device)
    outputs = model(inputs.to(device))
    if isinstance(outputs, Mapping):
        logits = outputs["out"] if "out" in outputs else outputs["logits"]
        main = criterion(logits, targets)
        if "aux" in outputs:
            auxiliary = criterion(outputs["aux"], targets)
            return main + aux_weight * auxiliary, {
                "main_loss": main,
                "aux_loss": auxiliary,
            }
        return main, {}
    return criterion(outputs, targets), {}


def model_loss(
    model: nn.Module, batch: tuple[list[torch.Tensor], list[dict[str, Any]]]
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Compute a TorchVision detector's native named training losses.

    Parameters
    ----------
    model : nn.Module
        Detector returning a loss dictionary when trained with targets.
    batch : tuple[list[Tensor], list[dict]]
        Images and model-native target dictionaries, already collated.

    Returns
    -------
    tuple[Tensor, dict[str, Tensor]]
        Sum of native loss terms and the original named terms.
    """
    device = next(model.parameters()).device
    images, targets = batch
    images = [image.to(device) for image in images]
    targets = [
        {
            key: value.to(device) if isinstance(value, torch.Tensor) else value
            for key, value in target.items()
        }
        for target in targets
    ]
    terms = model(images, targets)
    return sum(terms.values()), terms


def huggingface_loss(
    model: nn.Module, batch: Mapping[str, Any]
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Use a Transformers task model's weighted native loss and optional named terms.

    Parameters
    ----------
    model : nn.Module
        Task-head model accepting native keyword inputs and labels.
    batch : Mapping[str, Any]
        Prepared processor outputs and task-specific labels.

    Returns
    -------
    tuple[Tensor, dict[str, Tensor]]
        The provider's weighted total and optional unmodified component losses.
    """
    output = model(**to_device(batch, next(model.parameters()).device))
    return output.loss, output.get("loss_dict", {})


def ultralytics_loss(
    model: Any, batch: Any
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Execute the native Ultralytics criterion, including mask or keypoint supervision.

    Parameters
    ----------
    model : nn.Module
        Ultralytics task model with its native ``loss`` implementation.
    batch : dict or tuple
        Native batch dictionary, or image/label tensors for classification.

    Returns
    -------
    tuple[Tensor, dict[str, Tensor]]
        Sum of the provider's weighted loss vector and all native reporting terms.
    """
    from ultralytics.cfg import get_cfg
    from torchvision.transforms.v2.functional import to_dtype

    if isinstance(model.args, dict):
        model.args = get_cfg(model.args)
    if not isinstance(batch, Mapping):
        images, labels = batch
        batch = {"img": images, "cls": labels}
    native_batch = to_device(batch, next(model.parameters()).device)
    native_batch["img"] = to_dtype(native_batch["img"], torch.float32, scale=True)
    losses, terms = model.loss(native_batch)
    return losses.sum(), {
        f"native_loss_{index}": term for index, term in enumerate(terms.reshape(-1))
    }
