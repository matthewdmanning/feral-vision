"""Model registry workflow: register a model config and load its properties."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

from omegaconf import DictConfig, OmegaConf
from torch import nn

from feral_vision.models.ModelProperties import ModelProperties
from feral_vision.tasks import CVTask

_REGISTRY_PATH = Path("model_registry.json")


def register(name: str):
    """Register an in-repo ``nn.Module`` under ``name`` as a class decorator.

    Replaces ``models/registry.py``'s ``@register``: instead of populating an
    in-memory dict, writes a minimal ``"local"`` entry to ``model_registry.json``
    so the class becomes resolvable via :func:`model_builder`. Idempotent — the
    write only happens the first time ``name`` is seen, so importing the
    decorated class repeatedly (e.g. once per test process) does not re-write the
    registry file on every import.

    Parameters
    ----------
    name : str
        Registry key the decorated class is resolvable under
        (``cfg.architecture.id`` when ``cfg.architecture.source == "local"``).

    Returns
    -------
    Callable[[type], type]
        Decorator that registers and returns the class unchanged.
    """

    def decorator(cls: type) -> type:
        _ensure_local_registered(name, cls)
        return cls

    return decorator


def _load_registry() -> dict:
    """Return the full registry file contents, or an empty dict if it's missing."""
    if not _REGISTRY_PATH.exists():
        return {}
    return json.loads(_REGISTRY_PATH.read_text())


def _ensure_local_registered(name: str, cls: type) -> None:
    """Write a ``"local"`` registry entry for ``cls`` under ``name`` if absent.

    Parameters
    ----------
    name : str
        Registry key to check/write.
    cls : type
        The decorated in-repo ``nn.Module`` subclass; its dotted import path
        (``module.qualname``) is stored so :func:`_build_local` can re-import it
        without holding a live class reference in the (JSON) registry file.
    """
    registry = _load_registry()
    if name in registry:
        return
    registry[name] = {
        "config": {
            "architecture": {
                "source": "local",
                "id": name,
                "location": f"{cls.__module__}.{cls.__qualname__}",
            }
        },
        "model_outputs": [],
    }
    _REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


def registered_config(name: str) -> DictConfig:
    """Return the stored ``config`` sub-dict for a registered model.

    Unlike :func:`load_model_registry` (which only returns ``ModelProperties``),
    this exposes the full stored config — needed by :func:`model_builder` to read
    back ``architecture.source``/``architecture.location``.

    Parameters
    ----------
    name : str
        Registry key to look up.

    Returns
    -------
    DictConfig
        The registered model's stored ``config`` sub-dict.

    Raises
    ------
    KeyError
        If ``name`` is not in the registry.
    """
    registry = _load_registry()
    if name not in registry:
        raise KeyError(f"model {name!r} not in registry")
    return OmegaConf.create(registry[name]["config"])


def model_builder(cfg: DictConfig) -> nn.Module:
    """Build the ``nn.Module`` named by a model config's ``architecture``.

    Dispatches on ``cfg.architecture.source``: ``"local"`` resolves an in-repo
    architecture via the registry (see :func:`_build_local`); any other value is
    treated as an adapter-backed remote source and delegated to
    :func:`get_adapter`'s ``fetch``.

    Parameters
    ----------
    cfg : DictConfig
        A model config (``ModelConfig``-shaped): ``cfg.architecture.source``/
        ``.id`` select the source; ``cfg.weights`` (if set) is read by the
        adapter, not by this function.

    Returns
    -------
    nn.Module
        The constructed model.
    """
    source = cfg.architecture.source
    if source == "local":
        return _build_local(cfg)
    return get_adapter(source).fetch(cfg)


def _build_local(cfg: DictConfig) -> nn.Module:
    """Resolve and instantiate an in-repo architecture registered under ``cfg.architecture.id``.

    Parameters
    ----------
    cfg : DictConfig
        Model config with ``cfg.architecture.source == "local"``.

    Returns
    -------
    nn.Module
        A constructed instance of the registered class, built via
        ``cls.from_config(cfg)`` when available (falls back to ``cls()``).
    """
    dotted = registered_config(cfg.architecture.id).architecture.location
    module_path, _, class_name = dotted.rpartition(".")
    cls = getattr(importlib.import_module(module_path), class_name)
    return cls.from_config(cfg) if hasattr(cls, "from_config") else cls()


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

    from feral_vision.models.sources.SourceAdapter import SourceAdapter

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
