"""Model definitions gathered during prep, independent of MLflow tracking."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from omegaconf import DictConfig, OmegaConf

from sightkit_learn.config.schema import ModelConfig
from sightkit_learn.models.ModelProperties import ModelProperties
from sightkit_learn.tasks import CVTask


def model_definition(config: dict, model_outputs: list[str], metadata: dict) -> dict:
    """Use this function to validate gathered information before saving a prep definition."""
    cfg = OmegaConf.merge(OmegaConf.structured(ModelConfig), config)
    resolved = OmegaConf.to_container(cfg, resolve=True, throw_on_missing=True)
    for field in ("source", "id", "location"):
        if (
            not isinstance(resolved["architecture"][field], str)
            or not resolved["architecture"][field].strip()
        ):
            raise ValueError(f"architecture.{field} must be a nonempty string")
    return {
        "config": resolved,
        "model_outputs": [CVTask(task).value for task in model_outputs],
        "metadata": metadata,
    }


def save_model_definition(
    path: Path, name: str, entry: dict, *, overwrite: bool = False
) -> dict:
    """Use this function to preserve a validated prep definition in the offline JSON registry."""
    if not name.strip():
        raise ValueError("model name must be nonempty")
    entry = model_definition(**entry)
    registry = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if name in registry and not overwrite:
        raise ValueError(
            f"model {name!r} already exists; set overwrite=True to replace it"
        )
    registry[name] = entry
    payload = json.dumps(registry, indent=2, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(payload)
            stream.close()
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
    return entry


def load_model_definition(
    path: Path, name: str
) -> tuple[DictConfig, ModelProperties, dict]:
    """Use this function to recover prep information and its Hydra configuration without a provider call."""
    registry = json.loads(path.read_text(encoding="utf-8"))
    entry = registry[name]
    # Existing entries kept provider metadata beside config and model_outputs.
    metadata = entry.get(
        "metadata",
        {
            key: value
            for key, value in entry.items()
            if key not in {"config", "model_outputs"}
        },
    )
    return (
        OmegaConf.create(entry["config"]),
        ModelProperties(
            model_outputs=[CVTask(task) for task in entry["model_outputs"]]
        ),
        metadata,
    )
