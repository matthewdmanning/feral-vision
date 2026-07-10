"""Model inspector MCP server for feral-segmentor.

Tools:
  inspect_model     — call adapter.inspect() and return metadata JSON (no file writes)
  list_adapters     — scan sources/ for registered SOURCE_KEY adapters
  read_adapter      — return source code of a named adapter
  write_adapter     — write or overwrite an adapter file (to add new source support)
  search_hf_models  — search HuggingFace Hub by query / pipeline_tag
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()
SOURCES_DIR = PROJECT_ROOT / "src" / "feral_segmentor" / "models" / "sources"

sys.path.insert(0, str(PROJECT_ROOT / "src"))

mcp = FastMCP("model-inspector")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_adapters() -> dict[str, Path]:
    """Use this function to discover all registered source adapters by scanning SOURCES_DIR.

    Returns
    -------
    dict[str, Path]
        Mapping of SOURCE_KEY string to adapter file path for every ``*Adapter.py``
        file that defines a ``SOURCE_KEY`` module-level constant.
    """
    result: dict[str, Path] = {}
    for f in sorted(SOURCES_DIR.glob("*Adapter.py")):
        spec = importlib.util.spec_from_file_location(f.stem, f)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except Exception:
            continue
        key = getattr(mod, "SOURCE_KEY", None)
        if key:
            result[key] = f
    return result


def _resolve_adapter(source: str):
    """Use this function to load and instantiate the SourceAdapter subclass for a given source key.

    Parameters
    ----------
    source : str
        The SOURCE_KEY identifying the adapter (e.g. ``"hf_hub"``, ``"ultralytics"``).

    Returns
    -------
    SourceAdapter
        An instantiated adapter whose ``inspect()`` and ``fetch()`` methods are ready to call.

    Raises
    ------
    KeyError
        If no adapter file declares ``SOURCE_KEY = source``.
    RuntimeError
        If the adapter file is found but contains no ``SourceAdapter`` subclass.
    """
    from feral_segmentor.models.sources.SourceAdapter import SourceAdapter

    adapters = _load_adapters()
    if source not in adapters:
        raise KeyError(f"no adapter for {source!r}; available: {sorted(adapters)}")

    path = adapters[source]
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]

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
    raise RuntimeError(f"no SourceAdapter subclass found in {path}")


def _build_cfg(
    source: str,
    model_id: str,
    weights_id: list[str] | None,
    weights_location: str | None,
):
    """Use this function to construct an OmegaConf DictConfig in the shape expected by SourceAdapter.inspect().

    Parameters
    ----------
    source : str
        Adapter source key written into ``architecture.source`` and, when weights
        are provided, ``weights.source``.
    model_id : str
        Hub repo ID or local model filename; written into ``architecture.id``.
    weights_id : list[str] or None
        Weight filenames or hub asset names. When ``None``, the ``weights`` key is
        omitted from the config entirely.
    weights_location : str or None
        Local directory for caching downloaded weights; ``None`` means the hub loads
        directly into memory.

    Returns
    -------
    omegaconf.DictConfig
        A struct with ``architecture`` (and optionally ``weights``) keys matching
        ``SourceConfig`` / ``WeightsConfig`` from ``config/schema.py``.
    """
    from omegaconf import OmegaConf

    d: dict = {"architecture": {"source": source, "id": model_id, "location": None}}
    if weights_id:
        d["weights"] = {
            "source": source,
            "id": weights_id,
            "location": weights_location,
        }
    return OmegaConf.create(d)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def inspect_model(
    source: str,
    model_id: str,
    weights_id: list[str] | None = None,
    weights_location: str | None = None,
    fetch_if_needed: bool = False,
) -> str:
    """Use this function to inspect a model via its source adapter and return metadata as JSON.

    Does NOT write to ``model_registry.json`` — use ``scripts/register_model.py`` for that.

    Parameters
    ----------
    source : str
        Adapter source key (e.g. ``"hf_hub"``, ``"ultralytics"``, ``"torch_hub"``).
    model_id : str
        Hub repo ID or model filename (e.g. ``"facebook/detr-resnet-50"``).
    weights_id : list[str], optional
        Weight filenames or hub asset names.
    weights_location : str, optional
        Local directory for caching downloaded weights.
    fetch_if_needed : bool, optional
        When ``True``, downloads model weights to inspect architecture if hub
        metadata is unavailable. Defaults to ``False``.

    Returns
    -------
    str
        JSON string with keys ``model_outputs`` (list of CVTask values),
        ``n_classes`` (int or null), and ``metadata`` (hub-specific extras).
    """
    adapter = _resolve_adapter(source)
    cfg = _build_cfg(source, model_id, weights_id, weights_location)
    props, metadata = adapter.inspect(cfg, fetch_if_needed=fetch_if_needed)
    return json.dumps(
        {
            "model_outputs": [t.value for t in props.model_outputs],
            "n_classes": props.n_classes,
            "metadata": metadata,
        },
        indent=2,
    )


@mcp.tool()
def list_adapters() -> str:
    """Use this function to list all source adapters currently registered in sources/.

    Returns
    -------
    str
        JSON array of objects with keys ``source_key`` and ``file`` (relative path).
    """
    adapters = _load_adapters()
    rows = [
        {"source_key": k, "file": str(v.relative_to(PROJECT_ROOT))}
        for k, v in sorted(adapters.items())
    ]
    return json.dumps(rows, indent=2)


@mcp.tool()
def read_adapter(source_key: str) -> str:
    """Use this function to retrieve the full source code of a named adapter for inspection or reference.

    Parameters
    ----------
    source_key : str
        The ``SOURCE_KEY`` value declared by the adapter (e.g. ``"hf_hub"``, ``"ultralytics"``).

    Returns
    -------
    str
        Full UTF-8 source code of the adapter module.

    Raises
    ------
    KeyError
        If no adapter declares the given ``source_key``.
    """
    adapters = _load_adapters()
    if source_key not in adapters:
        raise KeyError(f"unknown adapter {source_key!r}; available: {sorted(adapters)}")
    return adapters[source_key].read_text(encoding="utf-8")


@mcp.tool()
def write_adapter(source_key: str, class_name: str, code: str) -> str:
    """Use this function to write or overwrite an adapter file when adding support for a new model source.

    Writes to ``src/feral_segmentor/models/sources/{class_name}Adapter.py``.
    The new adapter becomes available to ``inspect_model`` immediately after writing.

    Parameters
    ----------
    source_key : str
        The ``SOURCE_KEY`` the adapter will declare (e.g. ``"torchvision"``).
    class_name : str
        Stem used for both the class name and filename
        (e.g. ``"Torchvision"`` → ``TorchvisionAdapter.py``).
    code : str
        Full Python source of the adapter module. Must define ``SOURCE_KEY``
        and a ``SourceAdapter`` subclass.

    Returns
    -------
    str
        Relative path of the written file.
    """
    dest = SOURCES_DIR / f"{class_name}Adapter.py"
    dest.write_text(code, encoding="utf-8")
    return str(dest.relative_to(PROJECT_ROOT))


@mcp.tool()
def search_hf_models(
    query: str | None = None,
    pipeline_tag: str | None = None,
    limit: int = 10,
) -> str:
    """Use this function to search HuggingFace Hub for models by keyword or task type.

    Parameters
    ----------
    query : str, optional
        Free-text search term (model name, author, or keyword).
    pipeline_tag : str, optional
        Filter by task, e.g. ``"object-detection"``, ``"instance-segmentation"``,
        ``"semantic-segmentation"``, ``"image-classification"``, ``"pose-estimation"``.
    limit : int, optional
        Maximum number of results to return. Defaults to ``10``.

    Returns
    -------
    str
        JSON array of objects with keys ``id``, ``pipeline_tag``, ``downloads``,
        and ``tags`` (up to 5 per model), sorted by downloads descending.
    """
    from huggingface_hub import HfApi

    api = HfApi()
    kwargs: dict = {"limit": limit, "sort": "downloads", "direction": -1}
    if pipeline_tag:
        kwargs["pipeline_tag"] = pipeline_tag
    if query:
        kwargs["search"] = query

    models = list(api.list_models(**kwargs))
    rows = [
        {
            "id": m.id,
            "pipeline_tag": getattr(m, "pipeline_tag", None),
            "downloads": getattr(m, "downloads", None),
            "tags": list(getattr(m, "tags", []) or [])[:5],
        }
        for m in models
    ]
    return json.dumps(rows, indent=2)


if __name__ == "__main__":
    mcp.run()
