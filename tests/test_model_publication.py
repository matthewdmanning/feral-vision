"""Model publication preserves native CV contracts without running project inference."""

from collections import OrderedDict
from unittest.mock import create_autospec

import mlflow
import pytest
import torch
from torch import nn
from transformers.utils import ModelOutput
from torchvision.models._utils import IntermediateLayerGetter
from torchvision.models.segmentation import FCN

from feral_vision.training.tracking import log_model


@pytest.mark.parametrize("publication_fails", [False, True])
def test_publication_restores_frozen_submodule_modes(
    tmp_path, monkeypatch, publication_fails
):
    """Frozen BatchNorm remains in evaluation mode when its parent resumes training."""
    model = nn.Sequential(nn.Conv2d(3, 2, 1), nn.BatchNorm2d(2))
    model[1].eval()
    modes = [module.training for module in model.modules()]
    path = tmp_path / "best.pt"
    torch.save(model.state_dict(), path)
    publication = create_autospec(mlflow.pytorch.log_model, return_value="logged-model")
    if publication_fails:
        publication.side_effect = ConnectionError("offline")
    monkeypatch.setattr(mlflow.pytorch, "log_model", publication)

    if publication_fails:
        with pytest.raises(ConnectionError, match="offline"):
            log_model(model, path)
    else:
        log_model(model, path)

    assert [module.training for module in model.modules()] == modes


@pytest.mark.parametrize(
    "output",
    [
        torch.ones(2, 3),
        {"out": torch.ones(2, 3, 8, 8)},
        [{"boxes": torch.ones(1, 4), "scores": torch.ones(1)}],
        (torch.ones(2, 3), {"features": torch.ones(2, 3, 8, 8)}),
        ModelOutput(logits=torch.ones(2, 3)),
    ],
    ids=["classification", "semantic-mask", "instances", "tuple", "transformers"],
)
def test_publication_never_executes_or_converts_task_outputs(
    tmp_path, monkeypatch, output
):
    """Every reasonable inference output is irrelevant to native model serialization."""
    model = nn.Conv2d(3, 2, 1)
    path = tmp_path / "selected.pt"
    torch.save(model.state_dict(), path)
    selected = model.weight.detach().clone()
    with torch.no_grad():
        model.weight.add_(1)
    current = model.weight.detach().clone()
    forward = create_autospec(model.forward, return_value=output)
    monkeypatch.setattr(model, "forward", forward)
    observed = []

    def record(pytorch_model, **kwargs):
        observed.append(pytorch_model.weight.detach().clone())
        return "logged-model"

    publication = create_autospec(mlflow.pytorch.log_model, side_effect=record)
    monkeypatch.setattr(mlflow.pytorch, "log_model", publication)

    result = log_model(model, path)

    assert result == "logged-model"
    publication.assert_called_once_with(
        model,
        name="pytorch_model",
        serialization_format="pickle",
        input_example=None,
        signature=None,
        registered_model_name=None,
    )
    forward.assert_not_called()
    torch.testing.assert_close(observed[0], selected)
    torch.testing.assert_close(model.weight, current)
    assert model.training


def test_native_mlflow_roundtrip_preserves_semantic_segmentation_output(tmp_path):
    """A real structured-output model is logged without an example and reloads natively."""
    backbone = IntermediateLayerGetter(
        nn.Sequential(OrderedDict(conv=nn.Conv2d(3, 3, 1))),
        return_layers={"conv": "out"},
    )
    model = FCN(backbone, nn.Conv2d(3, 2, 1))
    path = tmp_path / "best.pt"
    torch.save(model.state_dict(), path)
    previous_uri = mlflow.get_tracking_uri()
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'tracking.db'}")
    try:
        experiment = mlflow.set_experiment("structured-publication")
        with mlflow.start_run(experiment_id=experiment.experiment_id):
            info = log_model(model, path)
        restored = mlflow.pytorch.load_model(info.model_uri)
    finally:
        mlflow.set_tracking_uri(previous_uri)

    images = torch.ones(2, 3, 8, 8)
    model.eval()
    with torch.no_grad():
        expected = model(images)
        actual = restored(images)
    assert set(actual) == {"out"}
    torch.testing.assert_close(actual, expected)


def test_publication_failure_restores_caller_weights_and_mode(tmp_path, monkeypatch):
    """A failed MLflow operation leaves the caller's in-memory training model intact."""
    model = nn.Conv2d(3, 2, 1)
    path = tmp_path / "selected.pt"
    torch.save(model.state_dict(), path)
    with torch.no_grad():
        model.weight.add_(1)
    current = {key: value.clone() for key, value in model.state_dict().items()}
    publication = create_autospec(
        mlflow.pytorch.log_model, side_effect=ConnectionError("offline")
    )
    monkeypatch.setattr(mlflow.pytorch, "log_model", publication)

    with pytest.raises(ConnectionError, match="offline"):
        log_model(model, path)

    torch.testing.assert_close(model.state_dict(), current)
    assert model.training
