"""Contracts for MLflow-backed model-definition registration and offline replay."""

from __future__ import annotations

import json
from types import SimpleNamespace

from omegaconf import OmegaConf

import feral_vision.models.register_model as registry
from feral_vision.models.ModelProperties import ModelProperties
from feral_vision.tasks import CVTask


class _FakeMlflowClient:
    """In-memory MLflow Registry client for registration-contract tests."""

    def __init__(self) -> None:
        self.models: dict[str, dict[str, str]] = {}

    def create_registered_model(self, name: str, tags: dict[str, str]) -> None:
        if name in self.models:
            raise ValueError("already exists")
        self.models[name] = dict(tags)

    def get_registered_model(self, name: str) -> SimpleNamespace:
        if name not in self.models:
            raise KeyError(name)
        return SimpleNamespace(tags=self.models[name])

    def set_registered_model_tag(self, name: str, key: str, value: str) -> None:
        self.models[name][key] = value


def _model_cfg():
    """Return the static definition metadata stored beside a registered model."""
    return OmegaConf.create(
        {
            "architecture": {
                "source": "local",
                "id": "net",
                "location": "feral_vision.models.default.Net",
            }
        }
    )


def test_register_model_stores_definition_metadata_in_mlflow(monkeypatch, tmp_path):
    """MLflow is the primary store for model-definition metadata."""
    client = _FakeMlflowClient()
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", tmp_path / "journal.json")
    monkeypatch.setattr(registry, "_mlflow_client", lambda: client)

    registry.register_model(
        "net",
        _model_cfg(),
        ModelProperties(model_outputs=[CVTask.CLASSIFICATION]),
        {"source": "test"},
    )

    assert json.loads(client.models["net"][registry._OUTPUTS_TAG]) == [
        CVTask.CLASSIFICATION.value
    ]
    assert registry.registered_config("net").architecture.location.endswith(".Net")
    assert registry.load_model_registry("net").model_outputs == [CVTask.CLASSIFICATION]


def test_register_model_queues_and_replays_when_mlflow_returns(monkeypatch, tmp_path):
    """An unavailable registry queues data temporarily and replays it later."""
    journal = tmp_path / "journal.json"
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", journal)
    monkeypatch.setattr(
        registry,
        "_mlflow_client",
        lambda: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    registry.register_model("net", _model_cfg(), ModelProperties())

    assert "net" in json.loads(journal.read_text())
    client = _FakeMlflowClient()
    monkeypatch.setattr(registry, "_mlflow_client", lambda: client)

    assert registry.load_model_registry("net").model_outputs == []
    assert "net" in client.models
    assert json.loads(journal.read_text()) == {}
