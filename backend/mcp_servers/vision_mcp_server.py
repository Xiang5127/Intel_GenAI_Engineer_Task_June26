"""Vision MCP server (Phase 5).

Local MCP server (official Python SDK, ``FastMCP`` + stdio) exposing vision
tools backed by the OpenVINO-or-fallback vision runtime. Spawned as a subprocess
by the MCP Client Manager.

Tools:
- ``detect_objects(frame_paths, conf=0.5)``
- ``count_objects(frame_paths, target, conf=0.5)``
- ``run_ocr(frame_paths)``
- ``detect_graphs(frame_paths)``

Run directly for debugging:
    python -m backend.mcp_servers.vision_mcp_server
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from mcp.server.fastmcp import FastMCP

from backend.services import vision_analysis

mcp = FastMCP("vision-mcp-server")


@contextmanager
def _protect_stdio() -> Iterator[None]:
    """Redirect OS-level stdout (fd 1) to stderr during noisy native work.

    The stdio transport uses stdout for JSON-RPC framing; native libs (OpenVINO /
    OpenCV) may emit stray bytes to stdout, corrupting the protocol. Restore
    before returning so FastMCP can serialize the response.
    """
    sys.stdout.flush()
    saved_fd = os.dup(1)
    try:
        os.dup2(2, 1)
        yield
    finally:
        sys.stdout.flush()
        os.dup2(saved_fd, 1)
        os.close(saved_fd)


@mcp.tool()
def detect_objects(frame_paths: list[str], conf: float = 0.5) -> dict[str, Any]:
    """Detect objects across frames; returns per-frame detections + label counts."""
    with _protect_stdio():
        return vision_analysis.detect_objects(frame_paths, conf=conf)


@mcp.tool()
def count_objects(frame_paths: list[str], target: str, conf: float = 0.5) -> dict[str, Any]:
    """Count occurrences of a target object label across frames."""
    with _protect_stdio():
        return vision_analysis.count_objects(frame_paths, target, conf=conf)


@mcp.tool()
def run_ocr(frame_paths: list[str]) -> dict[str, Any]:
    """Extract on-screen text from frames (OCR)."""
    with _protect_stdio():
        return vision_analysis.run_ocr(frame_paths)


@mcp.tool()
def detect_graphs(frame_paths: list[str], ocr_texts: Optional[list[str]] = None) -> dict[str, Any]:
    """Heuristically detect charts/graphs across frames."""
    with _protect_stdio():
        return vision_analysis.detect_graphs(frame_paths, ocr_texts=ocr_texts)


def main() -> None:
    # Initialize native runtimes on the MAIN thread before serving (FastMCP runs
    # sync tools in a worker thread, where native lib init can deadlock).
    with _protect_stdio():
        vision_analysis.warmup()
    mcp.run()


if __name__ == "__main__":
    main()
