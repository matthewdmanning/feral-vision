"""MLflow-backed model-definition registration with an offline replay journal."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import tempfile
from typing import Any

from omegaconf import DictConfig, OmegaConf
from torch import nn

from feral_vision.models.ModelProperties import ModelProperties
from feral_vision.tasks import CVTask
from feral_vision.utils import get_logger


logger = get_logger(__name__)
_OFFLINE_REGISTRY_PATH = (
    Path(tempfile.gettempdir()) / "feral-vision-mlflow-registry.json"
)
_CONFIG_TAG = "feral_vision.model_config"
_OUTPUTS_TAG = "feral_vision.model_outputs"
_METADATA_TAG = "feral_vision.model_metadata"


def register(name: str):
    """Mark an in-repository ``nn.Module`` as constructible from its config."""

    def decorator(cls: type) -> type:
        return cls

    return decorator


def _load_offline_registry() -> dict[str, dict[str, Any]]:
    if not _OFFLINE_REGISTRY_PATH.exists():
        return {}
    return json.loads(_OFFLINE_REGISTRY_PATH.read_text())


def _write_offline_registry(registry: dict[str, dict[str, Any]]) -> None:
    _OFFLINE_REGISTRY_PATH.write_text(json.dumps(registry, indent=2, sort_keys=True))


def _entry(
    cfg: DictConfig, properties: ModelProperties, metadata: dict | None = None
) -> dict[str, Any]:
    return {
        "config": OmegaConf.to_container(cfg, resolve=True),
        "model_outputs": [task.value for task in properties.model_outputs],
        "metadata": metadata or {},
    }


def _mlflow_client():
    import mlflow

    tracking_uri = mlflow.get_tracking_uri()
    if tracking_uri.startswith(("file:", "sqlite:")):
        raise ConnectionError("MLflow cloud tracking is not configured")
    return mlflow.tracking.MlflowClient()


def _store_in_mlflow(name: str, entry: dict[str, Any]) -> None:
    client = _mlflow_client()
    tags = {
        _CONFIG_TAG: json.dumps(entry["config"], sort_keys=True),
        _OUTPUTS_TAG: json.dumps(entry["model_outputs"]),
        _METADATA_TAG: json.dumps(entry["metadata"], sort_keys=True),
    }
    try:
        client.create_registered_model(name, tags=tags)
    except Exception:
        client.get_registered_model(name)
        for key, value in tags.items():
            client.set_registered_model_tag(name, key, value)


def _flush_offline_registry() -> None:
    offline = _load_offline_registry()
    for name, entry in list(offline.items()):
        _store_in_mlflow(name, entry)
        del offline[name]
    _write_offline_registry(offline)


def _store_or_journal(name: str, entry: dict[str, Any]) -> None:
    try:
        _flush_offline_registry()
        _store_in_mlflow(name, entry)
    except Exception:
        offline = _load_offline_registry()
        offline[name] = entry
        _write_offline_registry(offline)
        logger.warning(
            "MLflow model registry is unavailable; queued %s in %s",
            name,
            _OFFLINE_REGISTRY_PATH,
        )


def _entry_from_mlflow(name: str) -> dict[str, Any]:
    registered_model = _mlflow_client().get_registered_model(name)
    tags = dict(registered_model.tags)
    if _CONFIG_TAG not in tags or _OUTPUTS_TAG not in tags:
        raise KeyError(f"model {name!r} has no Feral Vision definition metadata")
    return {
        "config": json.loads(tags[_CONFIG_TAG]),
        "model_outputs": json.loads(tags[_OUTPUTS_TAG]),
        "metadata": json.loads(tags.get(_METADATA_TAG, "{}")),
    }


def _load_entry(name: str) -> dict[str, Any]:
    try:
        _flush_offline_registry()
        return _entry_from_mlflow(name)
    except Exception:
        offline = _load_offline_registry()
        if name not in offline:
            raise KeyError(
                f"model {name!r} is unavailable in MLflow or the offline journal"
            )
        return offline[name]


def registered_config(name: str) -> DictConfig:
    """Return a registered model's static configuration from MLflow or the journal."""
    return OmegaConf.create(_load_entry(name)["config"])


def model_builder(cfg: DictConfig) -> nn.Module:
    """Build an ``nn.Module`` from its configured architecture source."""
    if cfg.architecture.source == "local":
        return _build_local(cfg)
    return get_adapter(cfg.architecture.source).fetch(cfg)


def _build_local(cfg: DictConfig) -> nn.Module:
    """Instantiate an in-repository architecture from its required location."""
    module_path, _, class_name = cfg.architecture.location.rpartition(".")
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls.from_config(cfg) if hasattr(cls, "from_config") else cls()


def register_model(
    name: str,
    cfg: DictConfig,
    properties: ModelProperties,
    metadata: dict | None = None,
) -> None:
    """Register static model-definition metadata in MLflow or queue it offline."""
    _store_or_journal(name, _entry(cfg, properties, metadata))


def load_model_registry(name: str) -> ModelProperties:
    """Read registered model outputs from MLflow or the offline journal."""
    entry = _load_entry(name)
    return ModelProperties(
        model_outputs=[CVTask(task) for task in entry.get("model_outputs", [])]
    )


def get_adapter(source: str):
    """Return the ``SourceAdapter`` registered for ``source``."""
    return _get_adapter(source)


def _get_adapter(source: str):
    import importlib.util

    from feral_vision.models.sources.SourceAdapter import SourceAdapter

    sources_dir = Path(__file__).parent / "sources"
    for file_path in sorted(sources_dir.glob("*Adapter.py")):
        spec = importlib.util.spec_from_file_location(file_path.stem, file_path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception:
            continue
        if getattr(module, "SOURCE_KEY", None) != source:
            continue
        for name in dir(module):
            candidate = getattr(module, name)
            try:
                if (
                    isinstance(candidate, type)
                    and issubclass(candidate, SourceAdapter)
                    and candidate is not SourceAdapter
                ):
                    return candidate()
            except Exception:
                continue
    raise KeyError(
        f"no adapter for source {source!r}; add SOURCE_KEY = {source!r} to {sources_dir}"
    )
