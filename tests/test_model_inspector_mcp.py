"""Verify the model inspector starts and serves adapter tools over MCP 2 stdio."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp.client.stdio import stdio_client

from mcp import ClientSession, StdioServerParameters

# ---------------------------------------------------------------------------
# Helpers / local fixtures
# ---------------------------------------------------------------------------


async def _exercise_server(project_root: Path) -> None:
    """Use this function to verify adapter tools through the real stdio server."""
    server_path = Path(__file__).resolve().parents[1] / "mcp/server/main.py"
    sources = project_root / "src/feral_vision/models/sources"
    sources.mkdir(parents=True)
    adapter_code = 'SOURCE_KEY = "example"\n'
    (sources / "ExampleAdapter.py").write_text(adapter_code)
    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
        env={**os.environ, "PROJECT_ROOT": str(project_root)},
    )
    async with (
        stdio_client(parameters) as (read, write),
        ClientSession(read, write) as session,
    ):
        await session.initialize()
        tools = await session.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "inspect_model",
            "list_adapters",
            "read_adapter",
            "write_adapter",
            "search_hf_models",
        }
        listed = await session.call_tool("list_adapters", {})
        assert not listed.is_error
        assert json.loads(listed.content[0].text) == [
            {
                "source_key": "example",
                "file": "src/feral_vision/models/sources/ExampleAdapter.py",
            }
        ]
        read_result = await session.call_tool("read_adapter", {"source_key": "example"})
        assert not read_result.is_error
        assert read_result.content[0].text == adapter_code
        new_code = 'SOURCE_KEY = "new"\n'
        written = await session.call_tool(
            "write_adapter",
            {"source_key": "new", "class_name": "New", "code": new_code},
        )
        assert not written.is_error
        assert (sources / "NewAdapter.py").read_text() == new_code
        missing = await session.call_tool("read_adapter", {"source_key": "missing"})
        assert missing.is_error
        assert "unknown adapter" in missing.content[0].text


# ---------------------------------------------------------------------------
# Stdio tool contract
# ---------------------------------------------------------------------------


def test_model_inspector_serves_adapter_tools_over_stdio(tmp_path: Path) -> None:
    """Use this function to catch server startup and tool protocol regressions."""
    asyncio.run(asyncio.wait_for(_exercise_server(tmp_path), timeout=20))
