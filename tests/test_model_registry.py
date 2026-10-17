"""Verify MLflow model metadata persists and replays through the offline journal."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import create_autospec

import pytest
from mlflow.tracking import MlflowClient
from omegaconf import DictConfig, OmegaConf

import sightkit_learn.models.register_model as registry
from sightkit_learn.models.ModelProperties import ModelProperties
from sightkit_learn.tasks import CVTask


@pytest.fixture
def mlflow_client(tmp_path: Path) -> MlflowClient:
    """Provide an isolated real MLflow registry without a server or credentials."""
    uri = f"sqlite:///{tmp_path / 'registry.db'}"
    return MlflowClient(tracking_uri=uri, registry_uri=uri)


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
                "location": "sightkit_learn.models.default.Net",
            }
        }
    )
    return name, cfg, ModelProperties(model_outputs=outputs), metadata


def test_register_model_persists_and_reads_definition_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    mlflow_client: MlflowClient,
    model_definition: tuple[str, DictConfig, ModelProperties, dict],
) -> None:
    name, cfg, properties, metadata = model_definition
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", tmp_path / "journal.json")
    monkeypatch.setattr(registry, "_mlflow_client", lambda: mlflow_client)

    registry.register_model(name, cfg, properties, metadata)

    tags = mlflow_client.get_registered_model(name).tags
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
    mlflow_client: MlflowClient,
    model_definition: tuple[str, DictConfig, ModelProperties, dict],
) -> None:
    name, cfg, properties, metadata = model_definition
    journal = tmp_path / "journal.json"
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", journal)
    monkeypatch.setattr(
        registry,
        "_mlflow_client",
        create_autospec(
            registry._mlflow_client, side_effect=ConnectionError("offline")
        ),
    )

    registry.register_model(name, cfg, properties, metadata)

    assert name in json.loads(journal.read_text())
    monkeypatch.setattr(registry, "_mlflow_client", lambda: mlflow_client)
    assert registry.load_model_registry(name).model_outputs == properties.model_outputs
    assert (
        json.loads(
            mlflow_client.get_registered_model(name).tags[registry._METADATA_TAG]
        )
        == metadata
    )
    assert json.loads(journal.read_text()) == {}


def test_reregister_model_updates_existing_definition_metadata(
    monkeypatch, tmp_path, mlflow_client, model_definition
) -> None:
    """Re-registering an existing MLflow model replaces its definition tags."""
    name, cfg, properties, metadata = model_definition
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", tmp_path / "journal.json")
    monkeypatch.setattr(registry, "_mlflow_client", lambda: mlflow_client)
    registry.register_model(name, cfg, properties, metadata)
    updated_cfg = OmegaConf.merge(cfg, {"architecture": {"id": "updated"}})
    updated_properties = ModelProperties(model_outputs=[CVTask.DETECTION])

    registry.register_model(name, updated_cfg, updated_properties, {"revision": 2})

    assert registry.registered_config(name) == updated_cfg
    assert registry.load_model_registry(name).model_outputs == [CVTask.DETECTION]
    tags = mlflow_client.get_registered_model(name).tags
    assert json.loads(tags[registry._METADATA_TAG]) == {"revision": 2}
