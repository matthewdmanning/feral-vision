"""Exercise real prepared datasets across training and labeled inference."""

from operator import attrgetter
import json
from unittest.mock import create_autospec

import mlflow
import pandas as pd
import pytest
import torch
from omegaconf import OmegaConf
from torch import nn
from torchvision.io import write_png
from torch.utils.data import DataLoader, TensorDataset

from feral_vision.config.schema import InferenceConfig, TrainConfig
from feral_vision.inference import build_dataloader, build_predictor
from feral_vision.data.batching import collate_huggingface
from feral_vision.training.trainer import Trainer
from feral_vision.training.execution import prediction_loss
from feral_vision.training.trainer import build_dataloader as build_training_dataloader


@pytest.fixture
def paired_payload(tmp_path):
    """Write actual RGB images and class masks in the existing paired layout."""
    (tmp_path / "images").mkdir()
    (tmp_path / "annotations").mkdir()
    for index in range(3):
        write_png(
            torch.full((3, 8, 8), 64 + index, dtype=torch.uint8),
            str(tmp_path / "images" / f"sample_{index}.png"),
        )
        write_png(
            torch.full((1, 8, 8), index % 2, dtype=torch.uint8),
            str(tmp_path / "annotations" / f"sample_{index}.png"),
        )
    return tmp_path


@pytest.fixture
def model_loader(monkeypatch):
    """Mock retrieval only; use a real local model for forward execution."""
    model = nn.Conv2d(3, 2, 1).eval()
    load = create_autospec(mlflow.pytorch.load_model, return_value=model)
    monkeypatch.setattr(mlflow.pytorch, "load_model", load)
    return model, load


@pytest.mark.parametrize(
    "dataset_class", ["AnnotationDataset", "StreamingAnnotationDataset"]
)
def test_existing_paired_dataset_trains_and_predicts_with_ground_truth(
    paired_payload, tmp_path, model_loader, dataset_class
):
    """The same prepared image/mask batches work in training and labeled inference."""
    specification = {
        "_target_": "torch.utils.data.DataLoader",
        "_convert_": "all",
        "batch_size": 2,
        "dataset": {
            "_target_": f"feral_vision.data.dataset.{dataset_class}",
            "source": {
                "_target_": "feral_vision.io_utils.DatasetSource",
                "root": str(paired_payload),
            },
            "transform": {
                "_target_": "torchvision.transforms.v2.ToDtype",
                "dtype": {
                    "_target_": "hydra.utils.get_object",
                    "path": "torch.float32",
                },
                "scale": True,
            },
            "target_transform": {
                "_target_": "torchvision.transforms.v2.Compose",
                "transforms": [
                    {"_target_": "operator.itemgetter", "_args_": [0]},
                    {"_target_": "operator.attrgetter", "_args_": ["mask"]},
                    {
                        "_target_": "torch.as_tensor",
                        "_partial_": True,
                        "dtype": {
                            "_target_": "hydra.utils.get_object",
                            "path": "torch.int64",
                        },
                    },
                ],
            },
        },
    }
    cfg = OmegaConf.create(
        {
            "train": OmegaConf.structured(
                TrainConfig(dataloader=specification, loss_mode="prediction", epochs=1)
            ),
            "inference": OmegaConf.structured(
                InferenceConfig(model_uri="models:/vision/1", dataloader=specification)
            ),
        }
    )
    training_loader = build_training_dataloader(cfg)
    inference_loader = build_dataloader(cfg)
    for training_batch, inference_batch in zip(
        training_loader, inference_loader, strict=True
    ):
        torch.testing.assert_close(training_batch, inference_batch)

    model, load = model_loader
    trainer = Trainer(
        model,
        torch.optim.SGD(model.parameters(), lr=0.01),
        loss_fn=nn.CrossEntropyLoss(),
        cfg=cfg,
        best_model_path=tmp_path / "best.pt",
    )
    history = trainer.fit(training_loader)
    model.eval()
    results = list(build_predictor(cfg).predict_dataset(inference_loader))

    assert len(history["train_loss"]) == 1
    assert [len(predictions) for predictions, _ in results] == [2, 1]
    for (predictions, targets), (images, expected_targets) in zip(
        results, inference_loader, strict=True
    ):
        torch.testing.assert_close(targets, expected_targets)
        with torch.inference_mode():
            torch.testing.assert_close(predictions, model(images))
    load.assert_called_once()


def test_labeled_ragged_batches_keep_annotations_and_explicit_collator(
    paired_payload, model_loader
):
    """Dataset-selected collation retains annotation objects and ragged image sizes."""
    write_png(
        torch.ones(3, 10, 12, dtype=torch.uint8),
        str(paired_payload / "images" / "sample_2.png"),
    )
    write_png(
        torch.ones(1, 10, 12, dtype=torch.uint8),
        str(paired_payload / "annotations" / "sample_2.png"),
    )
    options = InferenceConfig(
        model_uri="models:/vision/1",
        collate_fn={"_target_": "torch.utils.data.default_collate", "_partial_": True},
        dataloader={
            "_target_": "torch.utils.data.DataLoader",
            "batch_size": 3,
            "dataset": {
                "_target_": "feral_vision.data.dataset.AnnotationDataset",
                "source": {
                    "_target_": "feral_vision.io_utils.DatasetSource",
                    "root": str(paired_payload),
                },
            },
            "collate_fn": {
                "_target_": "feral_vision.data.batching.collate_vision",
                "_partial_": True,
            },
        },
    )
    cfg = OmegaConf.create({"inference": OmegaConf.structured(options)})
    batch = next(iter(build_dataloader(cfg)))
    # A native vision model accepts the whole ragged image list.
    model = create_autospec(nn.Module, instance=True)
    output = [{"masks": torch.ones(1, 1, 8, 8)}]
    model.return_value = output
    model_loader[1].return_value = model

    predictions, targets = next(build_predictor(cfg).predict_dataset([batch]))

    assert predictions is output
    assert targets is batch[1]
    assert [image.shape[-2:] for image in model.call_args.args[0]] == [
        (8, 8),
        (8, 8),
        (10, 12),
    ]
    assert [annotations[0].mask.shape for annotations in targets] == [
        (8, 8),
        (8, 8),
        (10, 12),
    ]


def test_hydra_selectors_reuse_existing_detection_batch(paired_payload, model_loader):
    """Existing custom detection batches expose images and native ground truth explicitly."""
    for mask in (paired_payload / "annotations").glob("*.png"):
        mask.unlink()
        mask.with_suffix(".txt").write_text("0 0.5 0.5 0.25 0.25\n")
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(
                InferenceConfig(
                    model_uri="models:/vision/1",
                    input_selector={
                        "_target_": "operator.attrgetter",
                        "_args_": ["images"],
                    },
                    target_selector={
                        "_target_": "operator.attrgetter",
                        "_args_": ["batch_idx", "class_ids", "boxes"],
                    },
                    preprocess={
                        "_target_": "torchvision.transforms.v2.ToDtype",
                        "dtype": {
                            "_target_": "hydra.utils.get_object",
                            "path": "torch.float32",
                        },
                        "scale": True,
                    },
                    collate_fn={
                        "_target_": "feral_vision.training.detection.collate_detection",
                        "_partial_": True,
                        "num_classes": 2,
                    },
                    dataloader={
                        "_target_": "torch.utils.data.DataLoader",
                        "batch_size": 2,
                        "dataset": {
                            "_target_": "feral_vision.data.dataset.AnnotationDataset",
                            "source": {
                                "_target_": "feral_vision.io_utils.DatasetSource",
                                "root": str(paired_payload),
                            },
                        },
                    },
                )
            )
        }
    )
    batch = next(iter(build_dataloader(cfg)))

    predictions, targets = next(build_predictor(cfg).predict_dataset([batch]))

    assert predictions.shape == (2, 2, 8, 8)
    for actual, expected in zip(
        targets, attrgetter("batch_idx", "class_ids", "boxes")(batch), strict=True
    ):
        assert actual is expected


def test_prediction_only_stream_keeps_multi_input_tuple(model_loader):
    """Only the labeled dataset API splits inputs from targets."""
    model = create_autospec(nn.Module, instance=True)
    model_loader[1].return_value = model
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(
                InferenceConfig(model_uri="models:/vision/1")
            )
        }
    )
    inputs = (torch.ones(2, 3, 8, 8), torch.ones(2, 8, 8))

    list(build_predictor(cfg).predict_batches([inputs]))

    torch.testing.assert_close(model.call_args.args, inputs)


def test_huggingface_labeled_batches_reuse_collator_and_hydra_selectors(model_loader):
    """Native ragged HF targets remain separate from the selected pixel inputs."""
    samples = [
        {
            "pixel_values": torch.ones(3, 8, 8),
            "labels": {
                "boxes": torch.ones(count, 4),
                "class_labels": torch.ones(count, dtype=torch.long),
            },
        }
        for count in (1, 2)
    ]
    batch = next(
        iter(DataLoader(samples, batch_size=2, collate_fn=collate_huggingface))
    )
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(
                InferenceConfig(
                    model_uri="models:/vision/1",
                    input_selector={
                        "_target_": "operator.itemgetter",
                        "_args_": ["pixel_values"],
                    },
                    target_selector={
                        "_target_": "operator.itemgetter",
                        "_args_": ["labels"],
                    },
                )
            )
        }
    )

    predictions, targets = next(build_predictor(cfg).predict_dataset([batch]))

    assert predictions.shape == (2, 2, 8, 8)
    assert targets is batch["labels"]
    assert [target["boxes"].shape for target in targets] == [(1, 4), (2, 4)]


def test_distillation_targets_train_and_remain_soft_during_inference(
    model_loader, tmp_path
):
    """Standard TensorDataset teacher distributions require no project annotation class."""
    images = torch.ones(3, 3, 8, 8)
    teacher_probabilities = torch.full((3, 2, 8, 8), 0.25)
    teacher_probabilities[:, 0] = 0.75
    loader = DataLoader(TensorDataset(images, teacher_probabilities), batch_size=2)
    model = nn.Sequential(nn.Conv2d(3, 2, 1), nn.LogSoftmax(dim=1))
    before = model[0].weight.detach().clone()
    trainer = Trainer(
        model,
        torch.optim.SGD(model.parameters(), lr=0.01),
        loss_fn=nn.KLDivLoss(reduction="batchmean"),
        cfg=OmegaConf.create({"train": {"epochs": 1}}),
        best_model_path=tmp_path / "best.pt",
    )

    trainer.fit(loader)
    model.eval()
    model_loader[1].return_value = model
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(
                InferenceConfig(model_uri="models:/student/1")
            )
        }
    )
    results = list(build_predictor(cfg).predict_dataset(loader))

    assert not torch.equal(model[0].weight, before)
    torch.testing.assert_close(
        torch.cat([targets for _, targets in results]), teacher_probabilities
    )
    assert [len(predictions) for predictions, _ in results] == [2, 1]


def test_custom_annotation_structure_reaches_criterion_and_labeled_inference(
    model_loader,
):
    """Loading preserves arbitrary human/teacher structures for their configured consumers."""
    batch = next(
        iter(
            DataLoader(
                [
                    (
                        torch.ones(3, 8, 8),
                        {
                            "reviewer": "human",
                            "polygon": [[1.0, 1.0], [5.0, 1.0], [3.0, 5.0]],
                            "teacher": {"embedding": torch.ones(2, 8, 8)},
                        },
                    ),
                ],
                batch_size=1,
            )
        )
    )
    model, _ = model_loader
    criterion = create_autospec(nn.Module, instance=True)
    criterion.side_effect = lambda outputs, targets: nn.functional.mse_loss(
        outputs, targets["teacher"]["embedding"]
    )

    loss, _ = prediction_loss(model, batch, criterion=criterion)
    loss.backward()
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(
                InferenceConfig(model_uri="models:/vision/1")
            )
        }
    )
    _, targets = next(build_predictor(cfg).predict_dataset([batch]))

    assert model.weight.grad is not None
    received_targets = criterion.call_args.args[1]
    assert received_targets["reviewer"] == batch[1]["reviewer"]
    torch.testing.assert_close(received_targets["polygon"], batch[1]["polygon"])
    torch.testing.assert_close(received_targets["teacher"], batch[1]["teacher"])
    assert targets is batch[1]
    assert targets["reviewer"] == ["human"]


def test_torchvision_classification_dataset_predictions_reach_mlflow_accuracy(
    tmp_path, model_loader
):
    """Use ImageFolder and native MLflow evaluation on actual local image predictions."""
    (tmp_path / "annotations").mkdir()
    for name, value in (("dark", 0), ("light", 255)):
        folder = tmp_path / "images" / name
        folder.mkdir(parents=True)
        for index in range(2):
            write_png(
                torch.full((3, 8, 8), value, dtype=torch.uint8),
                str(folder / f"{index}.png"),
            )
    model = nn.Sequential(
        nn.AdaptiveAvgPool2d(1), nn.Flatten(), nn.Linear(3, 2, bias=False)
    ).eval()
    with torch.no_grad():
        model[-1].weight.copy_(torch.tensor([[-1.0, -1.0, -1.0], [1.0, 1.0, 1.0]]))
    model_loader[1].return_value = model
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(
                InferenceConfig(
                    model_uri="models:/vision/1",
                    postprocess={
                        "_target_": "torch.argmax",
                        "_partial_": True,
                        "dim": 1,
                    },
                    dataloader={
                        "_target_": "torch.utils.data.DataLoader",
                        "_convert_": "all",
                        "batch_size": 3,
                        "dataset": {
                            "_target_": "torchvision.datasets.ImageFolder",
                            "root": str(tmp_path / "images"),
                            "transform": {
                                "_target_": "torchvision.transforms.v2.Compose",
                                "transforms": [
                                    {"_target_": "torchvision.transforms.v2.ToImage"},
                                    {
                                        "_target_": "torchvision.transforms.v2.ToDtype",
                                        "dtype": {
                                            "_target_": "hydra.utils.get_object",
                                            "path": "torch.float32",
                                        },
                                        "scale": True,
                                    },
                                ],
                            },
                        },
                    },
                )
            )
        }
    )
    outputs = list(build_predictor(cfg).predict_dataset(build_dataloader(cfg)))
    evaluation_data = pd.DataFrame(
        {
            "prediction": torch.cat(
                [predictions for predictions, _ in outputs]
            ).tolist(),
            "target": torch.cat([targets for _, targets in outputs]).tolist(),
        }
    )
    previous_uri = mlflow.get_tracking_uri()
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'tracking.db'}")
    try:
        experiment = mlflow.MlflowClient().create_experiment(
            "accuracy", artifact_location=(tmp_path / "artifacts").as_uri()
        )
        with mlflow.start_run(experiment_id=experiment) as run:
            result = mlflow.models.evaluate(
                data=evaluation_data,
                predictions="prediction",
                targets="target",
                model_type="classifier",
                evaluators=["classifier"],
            )
        recorded = mlflow.MlflowClient().get_run(run.info.run_id).data.metrics
        assert result.metrics["accuracy_score"] == 1.0
        assert recorded["accuracy_score"] == 1.0
        assert result.metrics["example_count"] == 4
    finally:
        mlflow.set_tracking_uri(previous_uri)


def test_native_torchvision_coco_boxes_and_masks_share_training_inference_loader(
    paired_payload, model_loader
):
    """COCO JSON uses TorchVision's reader and v2 target wrapper without custom annotations."""
    annotation_path = paired_payload / "annotations" / "instances.json"
    annotation_path.write_text(
        json.dumps(
            {
                "images": [
                    {
                        "id": index,
                        "file_name": f"sample_{index}.png",
                        "width": 8,
                        "height": 8,
                    }
                    for index in range(3)
                ],
                "categories": [{"id": 3, "name": "animal"}],
                "annotations": [
                    {
                        "id": index + 1,
                        "image_id": index,
                        "category_id": 3,
                        "bbox": [1, 1, 4, 4],
                        "area": 16,
                        "iscrowd": 0,
                        "segmentation": [[1, 1, 5, 1, 5, 5, 1, 5]],
                    }
                    for index in range(3)
                ],
            }
        )
    )
    specification = {
        "_target_": "torch.utils.data.DataLoader",
        "_convert_": "all",
        "batch_size": 2,
        "dataset": {
            "_target_": "torchvision.datasets.wrap_dataset_for_transforms_v2",
            "target_keys": ["boxes", "labels", "masks"],
            "dataset": {
                "_target_": "torchvision.datasets.CocoDetection",
                "root": str(paired_payload / "images"),
                "annFile": str(annotation_path),
                "transforms": {
                    "_target_": "torchvision.transforms.v2.Compose",
                    "transforms": [
                        {"_target_": "torchvision.transforms.v2.ToImage"},
                        {
                            "_target_": "torchvision.transforms.v2.ToDtype",
                            "dtype": {
                                "_target_": "hydra.utils.get_object",
                                "path": "torch.float32",
                            },
                            "scale": True,
                        },
                    ],
                },
            },
        },
    }
    cfg = OmegaConf.create(
        {
            "train": OmegaConf.structured(
                TrainConfig(
                    task="instance_segmentation",
                    loss_mode="model",
                    dataloader=specification,
                )
            ),
            "inference": OmegaConf.structured(
                InferenceConfig(
                    model_uri="models:/vision/1",
                    dataloader=specification,
                    collate_fn={
                        "_target_": "feral_vision.data.batching.collate_vision",
                        "_partial_": True,
                    },
                )
            ),
        }
    )
    training_batch = next(iter(build_training_dataloader(cfg)))
    inference_batch = next(iter(build_dataloader(cfg)))
    torch.testing.assert_close(training_batch, inference_batch)
    images, native_targets = inference_batch
    torch.testing.assert_close(native_targets[0]["boxes"], torch.tensor([[1, 1, 5, 5]]))
    assert native_targets[0]["labels"].tolist() == [3]
    assert native_targets[0]["masks"].shape == (1, 8, 8)
    assert images[0].dtype == torch.float32
    assert images[0].max() <= 1
    model = create_autospec(nn.Module, instance=True)
    model.return_value = [
        {
            "boxes": target["boxes"],
            "labels": target["labels"],
            "masks": target["masks"],
            "scores": torch.ones(1),
        }
        for target in native_targets
    ]
    model_loader[1].return_value = model

    predictions, targets = next(build_predictor(cfg).predict_dataset([inference_batch]))

    assert predictions is model.return_value
    assert targets is native_targets
    torch.testing.assert_close(model.call_args.args, (images,))
