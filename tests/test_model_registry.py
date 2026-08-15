"""Verify MLflow model metadata persists and replays through the offline journal."""

from __future__ import annotations

import json

import mlflow
import pytest
from omegaconf import DictConfig, OmegaConf

import feral_vision.models.register_model as registry
from feral_vision.models.ModelProperties import ModelProperties
from feral_vision.tasks import CVTask


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
    mlflow_tracking_backend,
    model_definition: tuple[str, DictConfig, ModelProperties, dict],
) -> None:
    name, cfg, properties, metadata = model_definition
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", tmp_path / "journal.json")

    registry.register_model(name, cfg, properties, metadata)

    models = mlflow.search_logged_models(filter_string=f"name = '{name}'")
    assert len(models) == 1
    tags = mlflow.get_logged_model(models.iloc[0]["model_id"]).tags
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
    mlflow_tracking_backend,
    model_definition: tuple[str, DictConfig, ModelProperties, dict],
) -> None:
    name, cfg, properties, metadata = model_definition
    journal = tmp_path / "journal.json"
    monkeypatch.setattr(registry, "_OFFLINE_REGISTRY_PATH", journal)
    original_store = registry._store_in_mlflow

    def _offline_store(_name, _entry):
        raise ConnectionError("offline")

    monkeypatch.setattr(registry, "_store_in_mlflow", _offline_store)

    registry.register_model(name, cfg, properties, metadata)

    assert name in json.loads(journal.read_text())
    monkeypatch.setattr(registry, "_store_in_mlflow", original_store)
    assert registry.load_model_registry(name).model_outputs == properties.model_outputs
    models = mlflow.search_logged_models(filter_string=f"name = '{name}'")
    tags = mlflow.get_logged_model(models.iloc[0]["model_id"]).tags
    assert json.loads(tags[registry._METADATA_TAG]) == metadata
    assert json.loads(journal.read_text()) == {}
