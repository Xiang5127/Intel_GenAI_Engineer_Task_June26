"""MCP Client Manager (Phase 3, minimal).

Starts/connects to local MCP servers over the stdio transport using the official
Python MCP SDK and provides agents with a simple ``call_tool`` API. It is NOT the
orchestrator; it only owns connection lifecycle and tool invocation.

Each call spawns the target server, runs the tool, and tears the process down.
This keeps the MVP simple and stateless; pooling/long-lived sessions can be added
later without changing the agent-facing API.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Repository root (this file is backend/mcp_clients/mcp_client_manager.py).
REPO_ROOT = Path(__file__).resolve().parents[2]


def _child_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """Full parent environment for MCP subprocesses.

    The SDK's default stdio environment is a minimal whitelist, which can break
    libraries that rely on user env (e.g. huggingface_hub cache resolution).
    We pass the complete environment so subprocesses behave like a normal local
    process, plus HF_HUB_OFFLINE=1 so cached models load without a network check.
    """
    env = dict(os.environ)
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    env.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    if extra:
        env.update(extra)
    return env


@dataclass(frozen=True)
class MCPServerSpec:
    """How to launch a local MCP server as a subprocess."""

    name: str
    module: str  # e.g. "backend.mcp_servers.video_mcp_server"
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)

    def to_stdio_params(self) -> StdioServerParameters:
        return StdioServerParameters(
            command=sys.executable,
            args=["-m", self.module, *self.args],
            cwd=str(REPO_ROOT),
            env=_child_env(self.env),
        )


# Known local MCP servers. Extended as later phases add servers.
DEFAULT_SERVERS: dict[str, MCPServerSpec] = {
    "video": MCPServerSpec(name="video", module="backend.mcp_servers.video_mcp_server"),
    "transcription": MCPServerSpec(
        name="transcription", module="backend.mcp_servers.transcription_mcp_server"
    ),
}


class MCPClientManager:
    """Connects to local MCP servers and invokes their tools."""

    def __init__(self, servers: Optional[dict[str, MCPServerSpec]] = None) -> None:
        self._servers = dict(servers or DEFAULT_SERVERS)

    def register_server(self, spec: MCPServerSpec) -> None:
        self._servers[spec.name] = spec

    def _get_spec(self, server_name: str) -> MCPServerSpec:
        try:
            return self._servers[server_name]
        except KeyError as exc:
            raise KeyError(f"unknown MCP server: {server_name!r}") from exc

    async def list_tools(self, server_name: str) -> list[str]:
        """Return the tool names exposed by a server (connection sanity check)."""
        spec = self._get_spec(server_name)
        async with stdio_client(spec.to_stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [t.name for t in result.tools]

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """Spawn a server, invoke ``tool_name``, and return the structured result."""
        spec = self._get_spec(server_name)
        async with stdio_client(spec.to_stdio_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments or {})
                if result.isError:
                    text = _first_text(result) or "unknown MCP tool error"
                    raise MCPToolError(f"{server_name}.{tool_name} failed: {text}")
                return _extract_result(result)


class MCPToolError(Exception):
    """Raised when an MCP tool reports an error."""


def _first_text(result: Any) -> Optional[str]:
    for item in getattr(result, "content", []) or []:
        text = getattr(item, "text", None)
        if text:
            return text
    return None


def _extract_result(result: Any) -> dict[str, Any]:
    """Prefer structured content; fall back to parsing the first text block."""
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        # FastMCP wraps non-dict returns under "result"; dict returns pass through.
        return structured.get("result", structured) if "result" in structured else structured

    text = _first_text(result)
    if text is None:
        return {}
    import json

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
