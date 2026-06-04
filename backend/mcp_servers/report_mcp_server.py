"""Report MCP server (Phase 6).

Local MCP server (official Python SDK, ``FastMCP`` + stdio) exposing report
generation tools. Consumes the normalized ``report_data`` / ``slide_data``
structures and is agnostic to whether a rule-based or LLM summarizer produced
them. Spawned as a subprocess by the MCP Client Manager.

Tools:
- ``generate_pdf_report(report_data)``
- ``generate_pptx_report(slide_data)``

Run directly for debugging:
    python -m backend.mcp_servers.report_mcp_server
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator

from mcp.server.fastmcp import FastMCP

from backend.services import report_generator

mcp = FastMCP("report-mcp-server")


@contextmanager
def _protect_stdio() -> Iterator[None]:
    """Guard the stdio JSON-RPC channel from stray library stdout writes."""
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
def generate_pdf_report(report_data: dict[str, Any]) -> dict[str, Any]:
    """Generate a PDF from normalized report_data. Returns the output file path."""
    with _protect_stdio():
        return report_generator.generate_pdf_report(report_data)


@mcp.tool()
def generate_pptx_report(slide_data: dict[str, Any]) -> dict[str, Any]:
    """Generate a PPTX from normalized slide_data. Returns the output file path."""
    with _protect_stdio():
        return report_generator.generate_pptx_report(slide_data)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
