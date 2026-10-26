"""Model inspector MCP server for feral-vision.

Tools:
  inspect_model     — gather provider information and a Hydra model configuration
  list_models       — discover model identifiers through any registered provider
  save_model        — save gathered information to the offline prep registry
  get_model         — retrieve offline information and its Hydra YAML
  list_adapters     — scan sources/ for registered SOURCE_KEY adapters
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path
from itertools import islice

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", ".")).resolve()
SOURCES_DIR = PROJECT_ROOT / "src" / "sightkit_learn" / "models" / "sources"

sys.path.insert(0, str(PROJECT_ROOT / "src"))

mcp = MCPServer("model-inspector")


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
        except ImportError as exc:
            raise ToolError(f"cannot import adapter {f.name}: {exc}") from exc
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
    ToolError
        If no adapter file declares ``SOURCE_KEY = source``, or the adapter
        contains no ``SourceAdapter`` subclass.
    """
    from sightkit_learn.models.sources.SourceAdapter import SourceAdapter

    adapters = _load_adapters()
    if source not in adapters:
        raise ToolError(f"no adapter for {source!r}; available: {sorted(adapters)}")

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
    raise ToolError(f"no SourceAdapter subclass found in {path}")


def _build_cfg(
    source: str,
    model_id: str,
    weights_id: list[str] | None,
    weights_location: str | None,
    architecture_location: str | None = None,
    architecture_kwargs: dict | None = None,
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

    locations = {
        "hf_hub": f"https://huggingface.co/{model_id}",
        "ultralytics": "ultralytics.YOLO",
    }
    if source == "torch_hub" and not architecture_location:
        raise ToolError(
            "torch_hub requires architecture_location: the hubconf.py model entrypoint, such as resnet18"
        )
    d: dict = {
        "architecture": {
            "source": source,
            "id": model_id,
            "location": architecture_location or locations.get(source),
            "kwargs": architecture_kwargs or {},
        },
        "weights": None,
    }
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
def list_models(
    source: str,
    query: str | None = None,
    repository: str | None = None,
    filters: dict[str, str] | None = None,
    limit: int = 100,
    offset: int = 0,
) -> str:
    """Use this function to discover models from a registered provider before inspecting them.

    Parameters
    ----------
    source : str
        Registered adapter key: hf_hub, torch_hub, or ultralytics.
    query : str, optional
        Model name search. Ultralytics searches its installed catalogue.
    repository : str, optional
        Required Torch Hub owner/repo[:ref], or Hugging Face author filter.
    filters : dict[str, str], optional
        Exact-match fields reported by list_adapters. All providers support
        model_id and architecture_location; HF adds pipeline_tag and Ultralytics
        adds kind (architecture or checkpoint). Filtering precedes pagination.
    limit, offset : int
        Page size (1–1000) and zero-based offset. Follow next_offset for more.

    Returns
    -------
    str
        JSON models with model_id and architecture_location for inspect_model,
        plus next_offset when another page is available.
    """
    if not 1 <= limit <= 1000 or offset < 0:
        raise ToolError(
            "limit must be between 1 and 1000 and offset must be nonnegative"
        )
    adapter = _resolve_adapter(source)
    filters = filters or {}
    unsupported = filters.keys() - adapter.discovery_filters
    if unsupported:
        raise ToolError(
            f"unsupported {source} filters: {sorted(unsupported)}; supported: {sorted(adapter.discovery_filters)}"
        )
    try:
        with redirect_stdout(sys.stderr):
            candidates = adapter.list_models(
                query=query,
                repository=repository,
                pipeline_tag=filters.get("pipeline_tag"),
            )
            candidates = (
                row
                for row in candidates
                if all(row.get(key) == value for key, value in filters.items())
            )
            rows = list(islice(candidates, offset, offset + limit + 1))
    except Exception as exc:
        raise ToolError(f"could not list {source} models: {exc}") from exc
    return json.dumps(
        {
            "source": source,
            "models": rows[:limit],
            "next_offset": offset + limit if len(rows) > limit else None,
        },
        indent=2,
    )


@mcp.tool()
def inspect_model(
    source: str,
    model_id: str,
    weights_id: list[str] | None = None,
    weights_location: str | None = None,
    architecture_location: str | None = None,
    architecture_kwargs: dict | None = None,
) -> str:
    """Use this function to inspect a model via its source adapter and return metadata as JSON.

    Inspect provider information, then pass the result to ``save_model`` to
    retain it offline. Inspection does not contact MLflow or save a registry entry.
    Available provider weights are metadata; weights_id and constructor kwargs
    describe explicit setup choices, not automatically selected alternatives.

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
    architecture_location : str, optional
        Required Torch Hub entrypoint (for example ``resnet18``).
    architecture_kwargs : dict, optional
        Provider constructor options, such as Torch Hub ``weights=None``.

    Returns
    -------
    str
        JSON containing ``config``, ``model_outputs``, ``metadata`` and ``missing``.
        An empty outputs list is unknown, not an assertion of task support.
    """
    adapter = _resolve_adapter(source)
    cfg = _build_cfg(
        source,
        model_id,
        weights_id,
        weights_location,
        architecture_location,
        architecture_kwargs,
    )
    from omegaconf import OmegaConf

    try:
        # Provider summaries must not corrupt the MCP stdio transport.
        with redirect_stdout(sys.stderr):
            props, metadata = adapter.inspect(cfg)
    except Exception as exc:
        raise ToolError(
            f"could not inspect {source} model {model_id!r}: {exc}"
        ) from exc
    return json.dumps(
        {
            "config": OmegaConf.to_container(cfg, resolve=True),
            "model_outputs": [t.value for t in props.model_outputs],
            "metadata": metadata,
            "missing": []
            if props.model_outputs
            else [
                "model_outputs: task is unknown or has no CVTask mapping; see provider metadata"
            ],
        },
        indent=2,
    )


@mcp.tool()
def save_model(
    name: str,
    config: dict,
    model_outputs: list[str],
    metadata: dict,
    overwrite: bool = False,
) -> str:
    """Use this function to save an inspected model in models/registry/model_registry.json.

    Parameters
    ----------
    name : str
        Local registry name, including a variant when applicable.
    config, metadata : dict
        Configuration and provider metadata returned by inspect_model.
    model_outputs : list[str]
        Established CVTask values returned by inspection.
    overwrite : bool
        Explicitly replace an existing entry. Defaults to False.
    """
    from sightkit_learn.models.offline_registry import save_model_definition
    from omegaconf.errors import OmegaConfBaseException

    try:
        entry = save_model_definition(
            PROJECT_ROOT / "models/registry/model_registry.json",
            name,
            {"config": config, "model_outputs": model_outputs, "metadata": metadata},
            overwrite=overwrite,
        )
    except (ValueError, TypeError, OSError, OmegaConfBaseException) as exc:
        raise ToolError(f"could not save model {name!r}: {exc}") from exc
    return json.dumps({"name": name, **entry}, indent=2)


@mcp.tool()
def get_model(name: str) -> str:
    """Use this function to retrieve offline model information and Hydra YAML without provider access.

    Parameters
    ----------
    name : str
        Name previously saved in the prep registry.
    """
    from omegaconf import OmegaConf
    from sightkit_learn.models.offline_registry import load_model_definition

    try:
        cfg, props, metadata = load_model_definition(
            PROJECT_ROOT / "models/registry/model_registry.json", name
        )
    except (KeyError, ValueError, OSError) as exc:
        raise ToolError(f"could not read model {name!r}: {exc}") from exc
    return json.dumps(
        {
            "name": name,
            "config": OmegaConf.to_container(cfg, resolve=True),
            "model_outputs": [task.value for task in props.model_outputs],
            "metadata": metadata,
            "yaml": OmegaConf.to_yaml(cfg),
        },
        indent=2,
    )


@mcp.tool()
def list_adapters() -> str:
    """Use this function to list all source adapters currently registered in sources/.

    Returns
    -------
    str
        JSON array of provider keys and their accepted discovery filters.
    """
    adapters = _load_adapters()
    rows = [
        {"source_key": key, "filters": sorted(_resolve_adapter(key).discovery_filters)}
        for key in sorted(adapters)
    ]
    return json.dumps(rows, indent=2)


if __name__ == "__main__":
    mcp.run()
