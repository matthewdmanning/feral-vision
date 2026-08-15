"""Shared pytest fixtures for the test suite."""

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlparse

import pytest
import torch
from torch import nn

from feral_vision.data.dataset import AnnotationDataset
from feral_vision.io_utils import DatasetSource

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures"

_VALID_BBOX_FORMATS = frozenset({"cxcywh", "xyxy"})


@pytest.fixture(params=("sqlite", "legacy-file"))
def mlflow_tracking_backend(request, tmp_path, monkeypatch):
    """Provide isolated SQLite and legacy filesystem MLflow backends.

    The fixture uses MLflow's fluent tracking APIs for setup and keeps model
    registration mocked. Artifact uploads and downloaded model files remain
    real local filesystem transfers in both backend modes.
    """
    import mlflow

    import feral_vision.training.Trainer as trainer_module

    previous_tracking_uri = mlflow.get_tracking_uri()
    monkeypatch.chdir(tmp_path)
    mlflow.end_run()
    if request.param == "sqlite":
        monkeypatch.delenv("MLFLOW_ALLOW_FILE_STORE", raising=False)
        tracking_uri = f"sqlite:///{tmp_path / 'mlflow.db'}"
    else:
        monkeypatch.setenv("MLFLOW_ALLOW_FILE_STORE", "true")
        tracking_uri = (tmp_path / "mlruns").as_uri()

    experiment_name = f"trainer-tests-{request.param}"
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    experiment = mlflow.get_experiment_by_name(experiment_name)
    assert experiment is not None

    # Production accepts only deployed/local-server URIs. The fixture tests
    # MLflow's local backends without weakening that production contract.
    monkeypatch.setattr(trainer_module, "validate_tracking_uri", lambda uri: uri)

    registered_models = []

    def _register_model(model_uri, name):
        registered_models.append((model_uri, name))
        return SimpleNamespace(version="1")

    monkeypatch.setattr(mlflow, "register_model", _register_model)

    artifact_location = urlparse(experiment.artifact_location)
    yield SimpleNamespace(
        kind=request.param,
        tracking_uri=tracking_uri,
        experiment_name=experiment_name,
        artifact_root=Path(artifact_location.path),
        registered_models=registered_models,
    )

    mlflow.end_run()
    mlflow.set_tracking_uri(previous_tracking_uri)


@pytest.fixture(params=[FIXTURE_ROOT, str(FIXTURE_ROOT)])
def fixture_dataset_root(request):
    return request.param


@pytest.fixture
def fixture_dataset(fixture_dataset_root):
    return AnnotationDataset(DatasetSource(fixture_dataset_root))


@pytest.fixture
def trainer_fixture_dataset():
    """Single-root dataset fixture for tests that don't exercise DatasetSource's
    Path-vs-str root contract (see the parametrized fixture_dataset for that).
    """
    return AnnotationDataset(DatasetSource(FIXTURE_ROOT))


@pytest.fixture
def mask_to_tensor():
    def _mask_to_tensor(annotations):
        return torch.from_numpy(annotations[0].mask).long()

    return _mask_to_tensor


class _BBoxNet(nn.Module):
    """Tiny conv net regressing an image batch to ``(num_boxes, 4)`` box coordinates."""

    def __init__(
        self,
        in_channels: int,
        num_boxes: int,
        box_format: str,
        hidden_channels: int = 8,
    ) -> None:
        super().__init__()
        if box_format not in _VALID_BBOX_FORMATS:
            raise ValueError(
                f"box_format must be one of {sorted(_VALID_BBOX_FORMATS)}, got {box_format!r}"
            )
        self.box_format = box_format
        self.num_boxes = num_boxes
        self.backbone = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.AdaptiveAvgPool2d(1),
        )
        self.head = nn.Linear(hidden_channels, num_boxes * 4)

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        batch_size = images.shape[0]
        features = self.backbone(images).flatten(1)
        boxes = torch.sigmoid(self.head(features))
        return boxes.view(batch_size, self.num_boxes, 4)


@pytest.fixture
def bbox_net_factory():
    """Factory fixture building a tiny real (non-mocked) bbox-regression net.

    Returns a callable ``(in_channels=3, num_boxes=1, box_format="cxcywh") ->
    nn.Module`` producing real gradients, usable directly with Trainer.fit.
    """

    def _factory(
        in_channels: int = 3, num_boxes: int = 1, box_format: str = "cxcywh"
    ) -> _BBoxNet:
        return _BBoxNet(
            in_channels=in_channels, num_boxes=num_boxes, box_format=box_format
        )

    return _factory


@pytest.fixture
def image_model_factory():
    """Build tiny 2D image models and release their test state after each test."""
    models: list[nn.Module] = []

    def _factory(
        in_channels: int = 3, out_channels: int = 2, bias: bool = True
    ) -> nn.Conv2d:
        model = nn.Conv2d(in_channels, out_channels, kernel_size=1, bias=bias)
        models.append(model)
        return model

    yield _factory

    for model in models:
        model.zero_grad(set_to_none=True)
        model.to("cpu")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


@pytest.fixture
def image_model(image_model_factory):
    """Fresh default 2D image model for tests that only need parameters."""
    return image_model_factory()
