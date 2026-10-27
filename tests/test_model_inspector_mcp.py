"""Verify the model inspector starts and serves adapter tools over MCP 2 stdio."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import shutil
from pathlib import Path
from unittest.mock import create_autospec

import pytest

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Stdio tool contract
# ---------------------------------------------------------------------------


async def _exercise_prep(project_root: Path) -> None:
    """Use this function to exercise real adapters, registry files and Hydra through MCP stdio."""
    from omegaconf import DictConfig, OmegaConf
    from sightkit_learn.models.offline_registry import load_model_definition

    repo = Path(__file__).resolve().parents[1]
    shutil.copytree(
        repo / "src/sightkit_learn/models/sources",
        project_root / "src/sightkit_learn/models/sources",
    )
    source_contents = {
        path: path.read_bytes()
        for path in (project_root / "src/sightkit_learn/models/sources").glob("*.py")
    }
    bootstrap = project_root / "provider_boundaries.py"
    bootstrap.write_text(
        r"""from unittest.mock import create_autospec
import runpy, sys
import torch
import ultralytics
import huggingface_hub
from torch import nn
from sightkit_learn.models import register_model
register_model.load_model_registry = create_autospec(register_model.load_model_registry, side_effect=AssertionError("MLflow is outside prep"))
huggingface_hub.model_info = create_autospec(huggingface_hub.model_info, return_value=huggingface_hub.ModelInfo(id="test/classifier", pipeline_tag="image-classification", config={"num_labels": 2, "id2label": {"0": "cat", "1": "dog"}}, siblings=[{"rfilename": "model.safetensors"}]))
huggingface_hub.HfApi.list_models = create_autospec(huggingface_hub.HfApi.list_models, side_effect=lambda *args, **kwargs: iter([huggingface_hub.ModelInfo(id="test/classifier", pipeline_tag="image-classification")]))
import base64, io, json, urllib.request
hub_source = "from torchvision.models import resnet18\nraise AssertionError(\"repository code must not execute\")\n"
hub_document = {"content": base64.b64encode(hub_source.encode()).decode(), "html_url": "https://github.com/pytorch/vision/blob/v0.20.1/hubconf.py"}
urllib.request.urlopen = create_autospec(urllib.request.urlopen, side_effect=lambda *args, **kwargs: io.BytesIO(json.dumps(hub_document).encode()))
for operation in ("load", "help", "list"):
    setattr(torch.hub, operation, create_autospec(getattr(torch.hub, operation), side_effect=AssertionError("prep must not execute provider code")))
ultralytics.YOLO = create_autospec(ultralytics.YOLO, side_effect=AssertionError("prep must not construct a model"))
server = runpy.run_path(sys.argv[1])
server["mcp"].run()
""",
        encoding="utf-8",
    )
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(bootstrap), str(repo / "mcp/server/main.py")],
        env={**os.environ, "PROJECT_ROOT": str(project_root)},
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        providers = json.loads(
            (await session.call_tool("list_adapters", {})).content[0].text
        )
        assert {provider["source_key"] for provider in providers} == {
            "hf_hub",
            "torch_hub",
            "ultralytics",
        }
        tools = await session.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "list_adapters",
            "list_models",
            "inspect_model",
            "save_model",
            "get_model",
        }
        for provider in providers:
            assert "model_id" in provider["filters"]
        for source, model_id, location, expected_task in [
            ("hf_hub", "test/classifier", None, "classification"),
            ("torch_hub", "pytorch/vision:v0.20.1", "resnet18", "classification"),
            ("ultralytics", "yolo11n.pt", None, "detection"),
        ]:
            discovered = await session.call_tool(
                "list_models",
                {
                    "source": source,
                    "query": "yolo11n.pt" if source == "ultralytics" else None,
                    "repository": model_id if source == "torch_hub" else None,
                    "limit": 1,
                },
            )
            assert not discovered.is_error, discovered.content
            candidates = json.loads(discovered.content[0].text)["models"]
            assert len(candidates) == 1
            assert candidates[0]["model_id"] == model_id
            arguments = {
                "source": source,
                "model_id": candidates[0]["model_id"],
                "architecture_location": candidates[0]["architecture_location"],
            }
            inspected = await session.call_tool("inspect_model", arguments)
            assert not inspected.is_error, inspected.content
            entry = json.loads(inspected.content[0].text)
            assert entry.pop("missing") == []
            assert entry["model_outputs"] == [expected_task]
            assert entry["metadata"]
            assert entry["config"]["weights"] is None
            name = source + "-example"
            saved = await session.call_tool("save_model", {"name": name, **entry})
            assert not saved.is_error, saved.content
            retrieved = await session.call_tool("get_model", {"name": name})
            assert not retrieved.is_error, retrieved.content
            result = json.loads(retrieved.content[0].text)
            assert result["metadata"] == entry["metadata"]
            assert (
                OmegaConf.to_container(OmegaConf.create(result["yaml"]))
                == result["config"]
            )
            cfg, props, metadata = load_model_definition(
                project_root / "models/registry/model_registry.json", name
            )
            assert isinstance(cfg, DictConfig)
            assert cfg.architecture.source == source
            assert [task.value for task in props.model_outputs] == [expected_task]
            assert metadata == entry["metadata"]
        page = await session.call_tool(
            "list_models", {"source": "ultralytics", "query": "yolo11", "limit": 1}
        )
        first = json.loads(page.content[0].text)
        assert first["next_offset"] == 1
        page = await session.call_tool(
            "list_models",
            {
                "source": "ultralytics",
                "query": "yolo11",
                "limit": 1,
                "offset": first["next_offset"],
            },
        )
        second = json.loads(page.content[0].text)
        assert first["models"] != second["models"]
        no_repository = await session.call_tool("list_models", {"source": "torch_hub"})
        assert no_repository.is_error
        assert "requires repository" in no_repository.content[0].text
        unsupported = await session.call_tool(
            "list_models",
            {
                "source": "ultralytics",
                "filters": {"pipeline_tag": "image-classification"},
            },
        )
        assert unsupported.is_error
        assert "unsupported ultralytics filters" in unsupported.content[0].text
        for source, filters, repository in [
            ("hf_hub", {"pipeline_tag": "image-classification"}, None),
            (
                "torch_hub",
                {"architecture_location": "resnet18"},
                "pytorch/vision:v0.20.1",
            ),
            ("ultralytics", {"kind": "checkpoint"}, None),
        ]:
            result = await session.call_tool(
                "list_models",
                {
                    "source": source,
                    "filters": filters,
                    "repository": repository,
                    "query": "yolo11" if source == "ultralytics" else None,
                    "limit": 2,
                },
            )
            assert not result.is_error, result.content
            rows = json.loads(result.content[0].text)["models"]
            assert rows
            assert all(
                all(row[key] == value for key, value in filters.items()) for row in rows
            )
        refused = await session.call_tool(
            "inspect_model", {"source": "ultralytics", "model_id": "absent.pt"}
        )
        assert refused.is_error
        assert "no published architecture metadata" in refused.content[0].text
        path = project_root / "models/registry/model_registry.json"
        before = path.read_bytes()
        duplicate = await session.call_tool("save_model", {"name": name, **entry})
        assert duplicate.is_error
        assert "already exists" in duplicate.content[0].text
        assert path.read_bytes() == before
        invalid = await session.call_tool(
            "save_model",
            {"name": "invalid", **entry, "model_outputs": ["unsupported_task"]},
        )
        assert invalid.is_error
        assert "unsupported_task" in invalid.content[0].text
        assert path.read_bytes() == before
        unmapped = await session.call_tool(
            "save_model",
            {
                "name": "provider-task",
                **entry,
                "model_outputs": [],
                "metadata": {"task": "depth"},
            },
        )
        assert not unmapped.is_error, unmapped.content
        recovered = await session.call_tool("get_model", {"name": "provider-task"})
        assert not recovered.is_error, recovered.content
        recovered_entry = json.loads(recovered.content[0].text)
        assert recovered_entry["model_outputs"] == []
        assert recovered_entry["metadata"] == {"task": "depth"}
        assert all(
            path.read_bytes() == content for path, content in source_contents.items()
        )


def test_model_inspector_gathers_and_saves_all_providers_offline(
    tmp_path: Path,
) -> None:
    """Use this function to verify prep ends with provider metadata and usable Hydra config."""
    asyncio.run(asyncio.wait_for(_exercise_prep(tmp_path), timeout=60))


def test_offline_registry_preserves_saved_data_when_replacement_fails(
    tmp_path, monkeypatch
):
    """Use this function to verify a failed write cannot truncate gathered model information."""
    from sightkit_learn.models import offline_registry

    path = tmp_path / "model_registry.json"
    entry = {
        "config": {
            "architecture": {
                "source": "ultralytics",
                "id": "yolo11n.pt",
                "location": "ultralytics.YOLO",
            }
        },
        "model_outputs": ["detection"],
        "metadata": {"nc": 80},
    }
    offline_registry.save_model_definition(path, "detector", entry)
    before = path.read_bytes()
    replace = create_autospec(
        offline_registry.os.replace, side_effect=PermissionError("registry is locked")
    )
    monkeypatch.setattr(offline_registry.os, "replace", replace)
    with pytest.raises(PermissionError, match="registry is locked"):
        offline_registry.save_model_definition(path, "another-detector", entry)
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


def test_offline_registry_reads_existing_model_metadata(tmp_path: Path):
    """Use this function to keep existing prep entries readable without losing provider metadata."""
    from sightkit_learn.models.offline_registry import load_model_definition

    path = tmp_path / "model_registry.json"
    path.write_text(
        json.dumps(
            {
                "yolo11n-seg": {
                    "config": {
                        "architecture": {
                            "source": "ultralytics",
                            "id": "yolo11n-seg.pt",
                            "location": "ultralytics.YOLO",
                        }
                    },
                    "model_outputs": ["seg_instance"],
                    "nc": 2,
                    "names": {"0": "cat", "1": "dog"},
                }
            }
        ),
        encoding="utf-8",
    )
    cfg, props, metadata = load_model_definition(path, "yolo11n-seg")
    assert cfg.architecture.id == "yolo11n-seg.pt"
    assert [task.value for task in props.model_outputs] == ["seg_instance"]
    assert metadata["nc"] == 2
    assert len(metadata["names"]) == metadata["nc"]
