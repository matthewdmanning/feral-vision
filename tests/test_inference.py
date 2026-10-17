"""Native MLflow inference contracts; provider/model retrieval is mocked."""

from collections import OrderedDict
from unittest.mock import create_autospec

import mlflow
import numpy as np
import pytest
import torch
from mlflow.models import infer_signature
from omegaconf import OmegaConf
from torch import nn
from transformers.utils import ModelOutput
from torchvision.models._utils import IntermediateLayerGetter
from torchvision.models.segmentation import FCN

from sightkit_learn.config.schema import InferenceConfig
from sightkit_learn.inference import Predictor, build_predictor
from sightkit_learn.training.tracking import log_model


@pytest.fixture
def configured_model(monkeypatch):
    """Use an upstream API-checked loader and model without any remote retrieval."""
    model = create_autospec(nn.Module, instance=True)
    load = create_autospec(mlflow.pytorch.load_model, return_value=model)
    monkeypatch.setattr(mlflow.pytorch, "load_model", load)
    return model, load


@pytest.mark.parametrize(
    "output",
    [
        torch.ones(2, 3),
        {"out": torch.ones(2, 3, 8, 8)},
        [
            {
                "boxes": torch.ones(1, 4),
                "scores": torch.ones(1),
                "masks": torch.ones(1, 1, 8, 8),
            }
        ],
        {"keypoints": torch.ones(2, 17, 3)},
        (torch.ones(2, 3), {"features": torch.ones(2, 3, 8, 8)}),
        ModelOutput(logits=torch.ones(2, 3)),
    ],
    ids=[
        "classification",
        "semantic",
        "instances",
        "pose",
        "ultralytics-tuple",
        "transformers",
    ],
)
def test_predictions_preserve_exact_native_output_objects(configured_model, output):
    """Common CV output contracts are returned intact without task-specific coercion."""
    model, load = configured_model
    model.return_value = output
    predictor = Predictor("models:/vision@champion")
    inputs = torch.ones(2, 3, 8, 8)

    result = predictor.predict(inputs)

    assert result is output
    model.assert_called_once_with(inputs)
    load.assert_called_once_with(
        "models:/vision@champion", device="cpu", map_location="cpu"
    )
    model.eval.assert_not_called()


@pytest.mark.parametrize(
    "mode,inputs,expected_args,expected_kwargs",
    [
        (
            "auto",
            {"pixel_values": torch.ones(2, 3, 8, 8)},
            (),
            {"pixel_values": torch.ones(2, 3, 8, 8)},
        ),
        (
            "auto",
            [torch.ones(3, 8, 8), torch.ones(3, 10, 12)],
            ([torch.ones(3, 8, 8), torch.ones(3, 10, 12)],),
            {},
        ),
        (
            "auto",
            (torch.ones(2, 3, 8, 8), torch.ones(2, 8, 8)),
            (torch.ones(2, 3, 8, 8), torch.ones(2, 8, 8)),
            {},
        ),
        (
            "positional",
            {"image": torch.ones(3, 8, 8)},
            ({"image": torch.ones(3, 8, 8)},),
            {},
        ),
        ("args", [torch.ones(2, 3, 8, 8)], (torch.ones(2, 3, 8, 8),), {}),
        (
            "kwargs",
            {"pixel_values": torch.ones(2, 3, 8, 8)},
            (),
            {"pixel_values": torch.ones(2, 3, 8, 8)},
        ),
    ],
)
def test_prepared_input_calling_conventions(
    configured_model, mode, inputs, expected_args, expected_kwargs
):
    """Provider-native tensor, ragged image, and keyword inputs keep their call structure."""
    model, _ = configured_model
    predictor = Predictor(
        "models:/vision/1", call_mode=mode, forward_kwargs={"return_dict": True}
    )

    predictor.predict(inputs)

    model.assert_called_once()
    torch.testing.assert_close(model.call_args.args, expected_args)
    actual_keywords = model.call_args.kwargs.copy()
    return_dict_value = actual_keywords.pop("return_dict")
    assert return_dict_value is True
    torch.testing.assert_close(actual_keywords, expected_kwargs)


def test_hydra_configures_loading_processing_and_forward_options(
    configured_model, monkeypatch
):
    """Existing library processors and loader options are selected entirely through Hydra."""
    model, load = configured_model
    logits = torch.tensor([1.0, 2.0]).view(1, 2, 1, 1).expand(2, 2, 4, 4)
    model.return_value = logits
    tracking = create_autospec(mlflow.set_tracking_uri)
    monkeypatch.setattr(mlflow, "set_tracking_uri", tracking)
    options = InferenceConfig(
        model_uri="models:/vision/7",
        load_kwargs={"dst_path": "/cache"},
        forward_kwargs={"return_dict": True},
        preprocess={"_target_": "torchvision.transforms.v2.Resize", "size": [4, 4]},
        postprocess={"_target_": "torch.nn.Softmax", "dim": 1},
    )
    cfg = OmegaConf.create(
        {
            "inference": OmegaConf.structured(options),
            "tracking": {"tracking_uri": "https://tracking.example"},
        }
    )

    output = build_predictor(cfg).predict(torch.ones(2, 3, 8, 8))

    tracking.assert_called_once_with("https://tracking.example")
    load.assert_called_once_with(
        "models:/vision/7", device="cpu", map_location="cpu", dst_path="/cache"
    )
    assert model.call_args.args[0].shape == (2, 3, 4, 4)
    assert model.call_args.kwargs == {"return_dict": True}
    torch.testing.assert_close(output, logits.softmax(dim=1))


def test_inference_disables_autograd_and_loads_only_once(monkeypatch):
    """Repeated batches share one loaded model while prediction stays outside autograd."""
    model = nn.Conv2d(3, 2, 1).eval()
    load = create_autospec(mlflow.pytorch.load_model, return_value=model)
    monkeypatch.setattr(mlflow.pytorch, "load_model", load)
    predictor = Predictor("models:/vision/1")
    inputs = torch.ones(2, 3, 8, 8, requires_grad=True)
    original_grad_mode = torch.is_grad_enabled()

    stream = predictor.predict_batches([inputs, inputs])
    first, second = list(stream)

    assert first.is_inference() and second.is_inference()
    assert not first.requires_grad and not second.requires_grad
    assert torch.is_grad_enabled() == original_grad_mode
    load.assert_called_once()
    torch.testing.assert_close(first, second)


@pytest.mark.parametrize("serialization_format", ["pickle", "pt2"])
def test_published_registered_model_alias_roundtrip_preserves_structured_predictions(
    tmp_path, serialization_format
):
    """A model published through training is loaded natively by registry alias for inference."""
    backbone = IntermediateLayerGetter(
        nn.Sequential(OrderedDict(conv=nn.Conv2d(3, 3, 1))),
        return_layers={"conv": "out"},
    )
    model = FCN(backbone, nn.Conv2d(3, 2, 1)).eval()
    path = tmp_path / "best.pt"
    torch.save(model.state_dict(), path)
    images = torch.ones(2, 3, 8, 8)
    with torch.inference_mode():
        expected = model(images)
    previous_uri = mlflow.get_tracking_uri()
    tracking_uri = f"sqlite:///{tmp_path / 'tracking.db'}"
    mlflow.set_tracking_uri(tracking_uri)
    try:
        client = mlflow.tracking.MlflowClient(tracking_uri)
        experiment = client.create_experiment(
            "inference-tests", artifact_location=(tmp_path / "artifacts").as_uri()
        )
        example = (
            np.ones((2, 3, 8, 8), dtype=np.float32)
            if serialization_format == "pt2"
            else None
        )
        with mlflow.start_run(experiment_id=experiment):
            info = log_model(
                model,
                path,
                input_example=example,
                registered_model_name="vision",
                serialization_format=serialization_format,
                signature=infer_signature(example) if example is not None else None,
            )
        client.set_registered_model_alias(
            "vision", "champion", str(info.registered_model_version)
        )
        options = InferenceConfig(model_uri="models:/vision@champion")
        cfg = OmegaConf.create(
            {
                "inference": OmegaConf.structured(options),
                "tracking": {"tracking_uri": tracking_uri},
            }
        )

        predictor = build_predictor(cfg)
        actual = predictor.predict(images)

        assert mlflow.active_run() is None
        assert set(actual) == {"out"}
        torch.testing.assert_close(actual, expected)
    finally:
        mlflow.set_tracking_uri(previous_uri)
