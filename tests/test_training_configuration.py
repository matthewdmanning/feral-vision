"""Hydra-selected common CV paths consume prepared batches without retrieval."""

from unittest.mock import create_autospec

import pytest
import torch
from omegaconf import OmegaConf, open_dict
from torch import nn
from transformers import PreTrainedModel
from transformers.utils import ModelOutput
from torchvision.models.detection import FasterRCNN
from ultralytics.nn.tasks import BaseModel

from feral_vision.config.schema import (
    CrossEntropyConfig,
    ModelConfig,
    SGDConfig,
    SourceConfig,
    StepLRConfig,
    TrainConfig,
)
from feral_vision.models import register_model
from feral_vision.training.trainer import build_dataloader, build_trainer


@pytest.fixture
def configuration(tmp_path):
    """Construct the same structured Hydra contracts consumed by recipes."""
    train = OmegaConf.structured(TrainConfig())
    train.optim = OmegaConf.structured(SGDConfig(lr=0.01))
    train.scheduler = OmegaConf.structured(StepLRConfig(step_size=1))
    train.loss_fn = OmegaConf.structured(CrossEntropyConfig())
    train.epochs = 1
    train.device = "cpu"
    train.best_model_path = str(tmp_path / "best.pt")
    model = ModelConfig(
        architecture=SourceConfig(
            source="local", id="test", location="torch.nn.Identity"
        )
    )
    return OmegaConf.create({"train": train, "model": OmegaConf.structured(model)})


def _model_mock(model_class):
    """Provide real trainable parameters behind an upstream API-checked model mock."""
    model = create_autospec(model_class, instance=True)
    weights = nn.Parameter(torch.tensor([0.5, -0.5]))
    model.parameters.side_effect = lambda: iter([weights])
    model.to.return_value = model
    model.state_dict.side_effect = lambda: {"weight": weights.detach().clone()}
    return model, weights


@pytest.mark.parametrize("task", ["classification", "semantic_segmentation"])
def test_hydra_selects_tensor_or_structured_logits_and_trains(
    configuration, monkeypatch, task
):
    """Common external criteria need configuration, not a user-defined loss callback."""
    configuration.train.task = task
    model, weights = _model_mock(nn.Module)
    if task == "classification":
        logits = weights.view(1, 2).expand(2, 2)
        labels = torch.zeros(2, dtype=torch.long)
    else:
        logits = {"out": weights.view(1, 2, 1, 1).expand(2, 2, 8, 8)}
        logits["aux"] = logits["out"] * 0.5
        labels = torch.zeros(2, 8, 8, dtype=torch.long)
    model.return_value = logits
    factory = create_autospec(register_model.model_builder, return_value=model)
    monkeypatch.setattr(register_model, "model_builder", factory)
    before = weights.detach().clone()

    trainer = build_trainer(configuration)
    history = trainer.fit([(torch.ones(2, 3, 8, 8), labels)])

    factory.assert_called_once_with(configuration.model, task=task)
    assert not torch.equal(weights, before)
    assert len(history["train_loss"]) == 1
    assert trainer.best_model_path.is_file()
    if task == "semantic_segmentation":
        assert history["train_loss"][0] == pytest.approx(
            history["main_loss"][0] + 0.5 * history["aux_loss"][0]
        )


@pytest.mark.parametrize("task", ["detection", "instance_segmentation", "pose"])
def test_hydra_selects_torchvision_native_losses(configuration, monkeypatch, task):
    """Box, instance-mask, and keypoint models use their native loss dictionaries."""
    configuration.train.task = task
    model, weights = _model_mock(FasterRCNN)
    terms = {
        "loss_classifier": weights[0].square(),
        "loss_geometry": weights[1].square(),
    }
    model.return_value = terms
    monkeypatch.setattr(
        register_model,
        "model_builder",
        create_autospec(register_model.model_builder, return_value=model),
    )
    target = {
        "boxes": torch.tensor([[1.0, 1.0, 6.0, 6.0]]),
        "labels": torch.tensor([1]),
    }
    if task == "instance_segmentation":
        target["masks"] = torch.ones(1, 8, 8, dtype=torch.uint8)
    if task == "pose":
        target["keypoints"] = torch.ones(1, 17, 3)
    images, targets = [torch.ones(3, 8, 8)], [target]

    trainer = build_trainer(configuration)
    history = trainer.fit([(images, targets)])

    model.assert_called_once_with(images, targets)
    assert history["train_loss"] == pytest.approx([0.5])
    assert weights.grad is not None


@pytest.mark.parametrize(
    "task",
    [
        "classification",
        "detection",
        "semantic_segmentation",
        "instance_segmentation",
        "panoptic_segmentation",
        "pose",
    ],
)
def test_hydra_preserves_huggingface_weighted_native_loss(
    configuration, monkeypatch, task
):
    """Transformers owns weighting; the training loop must not re-sum its component reports."""
    configuration.model.architecture.source = "hf_hub"
    configuration.train.task = task
    model, weights = _model_mock(PreTrainedModel)
    components = {"first": weights[0].square(), "second": weights[1].square()}
    model.return_value = ModelOutput(
        loss=3 * components["first"] + components["second"], loss_dict=components
    )
    monkeypatch.setattr(
        register_model,
        "model_builder",
        create_autospec(register_model.model_builder, return_value=model),
    )
    inputs = {"pixel_values": torch.ones(2, 3, 8, 8)}
    if task in {"instance_segmentation", "panoptic_segmentation"}:
        inputs["class_labels"] = [torch.tensor([1]), torch.tensor([0, 1])]
        inputs["mask_labels"] = [torch.ones(1, 8, 8), torch.ones(2, 8, 8)]
    elif task == "detection":
        inputs["labels"] = [
            {
                "class_labels": torch.tensor([1]),
                "boxes": torch.tensor([[0.5, 0.5, 0.4, 0.4]]),
            }
            for _ in range(2)
        ]
    else:
        shapes = {
            "classification": (2,),
            "semantic_segmentation": (2, 8, 8),
            "pose": (2, 17, 8, 8),
        }
        inputs["labels"] = torch.zeros(
            shapes[task], dtype=torch.long if task != "pose" else torch.float32
        )

    history = build_trainer(configuration).fit([inputs])

    model.assert_called_once()
    torch.testing.assert_close(model.call_args.kwargs, inputs)
    assert history["train_loss"] == pytest.approx([1.0])
    assert history["first"] == pytest.approx([0.25])
    assert weights.grad is not None


@pytest.mark.parametrize(
    "task", ["classification", "detection", "instance_segmentation", "pose"]
)
def test_hydra_uses_native_ultralytics_mask_and_keypoint_losses(
    configuration, monkeypatch, task
):
    """Native task losses retain mask/keypoint targets and every weighted loss component."""
    configuration.model.architecture.source = "ultralytics"
    configuration.train.task = task
    if task == "detection":
        configuration.train.loss_mode = "ultralytics"
    model, weights = _model_mock(BaseModel)
    model.args = {}
    losses = weights.square()
    model.loss.return_value = losses, losses.detach()
    monkeypatch.setattr(
        register_model,
        "model_builder",
        create_autospec(register_model.model_builder, return_value=model),
    )
    inputs = {
        "img": torch.full((2, 3, 8, 8), 255, dtype=torch.uint8),
        "cls": torch.tensor([0, 1]),
    }
    if task == "instance_segmentation":
        inputs["masks"] = torch.ones(2, 8, 8)
    if task == "pose":
        inputs["keypoints"] = torch.ones(2, 17, 3)

    history = build_trainer(configuration).fit([inputs])

    model.loss.assert_called_once()
    native = model.loss.call_args.args[0]
    torch.testing.assert_close(native["img"], torch.ones(2, 3, 8, 8))
    for key in set(inputs) - {"img"}:
        torch.testing.assert_close(native[key], inputs[key])
    assert history["train_loss"] == pytest.approx([0.5])
    assert history["native_loss_0"] == pytest.approx([0.25])
    assert history["native_loss_1"] == pytest.approx([0.25])


def test_hydra_instantiates_prepared_dataset_and_dataloader(configuration):
    """Users can select an existing dataset/collator through Hydra without writing Python."""
    configuration.train.task = "classification"
    configuration.train.dataloader = {
        "_target_": "torch.utils.data.DataLoader",
        "_convert_": "all",
        "dataset": {
            "_target_": "torch.utils.data.TensorDataset",
            "_args_": [
                {"_target_": "torch.ones", "size": [2, 3, 8, 8]},
                {"_target_": "torch.tensor", "data": [0, 1]},
            ],
        },
        "batch_size": 2,
    }

    images, labels = next(iter(build_dataloader(configuration)))

    assert images.shape == (2, 3, 8, 8)
    torch.testing.assert_close(labels, torch.tensor([0, 1]))


def test_builder_binds_optimizer_and_weighted_criterion_after_device_placement(
    configuration,
):
    """Native meta placement exposes stale parameter bindings without requiring a GPU."""
    configuration.train.device = "meta"
    configuration.train.task = "classification"
    configuration.model.architecture.location = "torch.nn.Conv2d"
    configuration.model.architecture.kwargs = {
        "in_channels": 3,
        "out_channels": 2,
        "kernel_size": 1,
    }
    with open_dict(configuration.train.loss_fn):
        configuration.train.loss_fn.weight = {
            "_target_": "torch.ones",
            "_convert_": "all",
            "size": [2],
        }

    trainer = build_trainer(configuration)

    optimized = trainer.optimizer.param_groups[0]["params"]
    assert all(
        left is right
        for left, right in zip(optimized, trainer.model.parameters(), strict=True)
    )
    assert all(parameter.device.type == "meta" for parameter in optimized)
    assert trainer.loss_fn.weight.device.type == "meta"
