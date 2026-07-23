"""Verify MLflow model metadata persists and replays through the offline journal."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from omegaconf import DictConfig, OmegaConf

import feral_vision.models.register_model as registry
from feral_vision.models.ModelProperties import ModelProperties
from feral_vision.tasks import CVTask


class _FakeMlflowClient:
    """In-memory MLflow Registry client for model metadata tests."""

    def __init__(self) -> None:
        self.models: dict[str, dict[str, str]] = {}

    def create_registered_model(self, name: str, tags: dict[str, str]) -> None:
        """Create a registered model with metadata tags."""
        if name in self.models:
            raise ValueError("already exists")
        self.models[name] = dict(tags)

    def get_registered_model(self, name: str) -> SimpleNamespace:
        """Return one registered model's tags."""
        if name not in self.models:
            raise KeyError(name)
        return SimpleNamespace(tags=self.models[name])

    def set_registered_model_tag(self, name: str, key: str, value: str) -> None:
        """Update a registered model metadata tag."""
        self.models[name][key] = value


@pytest.fixture
def mlflow_client() -> _FakeMlflowClient:
    """Provide an isolated in-memory MLflow client."""
    return _FakeMlflowClient()


@pytest.fixture(
    params=[
        pytest.param(
            ("classifier", [CVTask.CLASSIFICATION], {"source": "test"}),
            id="classification",
        ),
        pytest.param(
            ("segmentor", [CVTask.SEG_SEMANTIC], {"source": "fixture", "revision": 3}),
            id="segmentation",
        ),
    ],
)
def model_definition(
    request: pytest.FixtureRequest,
) -> tuple[str, DictConfig, ModelProperties, dict]:
    """Provide model definition metadata that registration must preserve."""
    name, outputs, metadata = request.param
    cfg = OmegaConf.create(
        {
            "architecture": {
                "source": "local",
                "id": name,
                "location": "feral_vision.models.default.Net",
            }
        }
    )
    return name, cfg, ModelProperties(model_outputs=outputs), metadata


def test_register_model_persists_and_reads_definition_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    mlflow_client: _FakeMlflowClient,
    model_definition: tuple[str, DictConfig, ModelProperties, dict],
) -> None:
    name, cfg, properties, metadata = model_definition
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", tmp_path / "journal.json")
    monkeypatch.setattr(registry, "_mlflow_client", lambda: mlflow_client)

    registry.register_model(name, cfg, properties, metadata)

    tags = mlflow_client.models[name]
    assert json.loads(tags[registry._CONFIG_TAG]) == OmegaConf.to_container(
        cfg, resolve=True
    )
    assert json.loads(tags[registry._OUTPUTS_TAG]) == [
        task.value for task in properties.model_outputs
    ]
    assert json.loads(tags[registry._METADATA_TAG]) == metadata
    assert OmegaConf.to_container(
        registry.registered_config(name), resolve=True
    ) == OmegaConf.to_container(cfg, resolve=True)
    assert registry.load_model_registry(name).model_outputs == properties.model_outputs


def test_register_model_replays_offline_definition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    mlflow_client: _FakeMlflowClient,
    model_definition: tuple[str, DictConfig, ModelProperties, dict],
) -> None:
    name, cfg, properties, metadata = model_definition
    journal = tmp_path / "journal.json"
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", journal)
    monkeypatch.setattr(
        registry,
        "_mlflow_client",
        lambda: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    registry.register_model(name, cfg, properties, metadata)

    assert name in json.loads(journal.read_text())
    monkeypatch.setattr(registry, "_mlflow_client", lambda: mlflow_client)
    assert registry.load_model_registry(name).model_outputs == properties.model_outputs
    assert json.loads(mlflow_client.models[name][registry._METADATA_TAG]) == metadata
    assert json.loads(journal.read_text()) == {}
