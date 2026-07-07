"""Model registry workflow: register a model config and load its properties."""

from __future__ import annotations

import json
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from feral_segmentor.models.ModelProperties import ModelProperties
from feral_segmentor.tasks import CVTask

_REGISTRY_PATH = Path("model_registry.json")


def register_model(
    name: str,
    cfg: DictConfig,
    properties: ModelProperties,
    metadata: dict | None = None,
) -> None:
    """Write model config and properties to the registry file."""
    registry = json.loads(_REGISTRY_PATH.read_text())
    entry: dict = {
        "config": OmegaConf.to_container(cfg, resolve=True),
        "model_outputs": [t.value for t in properties.model_outputs],
    }
    if metadata:
        entry.update(metadata)
    registry[name] = entry
    _REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def load_model_registry(name: str) -> ModelProperties:
    """Read a registered model's properties from the registry file."""
    registry = json.loads(_REGISTRY_PATH.read_text())
    if name not in registry:
        raise KeyError(f"model {name!r} not in registry; call register_model() first")
    entry = registry[name]
    return ModelProperties(
        model_outputs=[CVTask(t) for t in entry.get("model_outputs", [])],
    )


def get_adapter(source: str):
    """Return the :class:`SourceAdapter` instance registered for ``source``.

    Public entrypoint over :func:`_get_adapter` for callers outside the registry
    workflow (e.g. the training stage, which needs only ``fetch``).
    """
    return _get_adapter(source)


def _get_adapter(source: str):
    import importlib.util

    from feral_segmentor.models.sources.SourceAdapter import SourceAdapter

    sources_dir = Path(__file__).parent / "sources"
    for f in sorted(sources_dir.glob("*Adapter.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
        except Exception:
            continue
        if getattr(mod, "SOURCE_KEY", None) != source:
            continue
        for name in dir(mod):
            obj = getattr(mod, name)
            try:
                if (
                    isinstance(obj, type)
                    and issubclass(obj, SourceAdapter)
                    and obj is not SourceAdapter
                ):
                    return obj()
            except Exception:
                continue
    raise KeyError(
        f"no adapter for source {source!r}; "
        f"add SOURCE_KEY = {source!r} to an adapter in {sources_dir}"
    )
