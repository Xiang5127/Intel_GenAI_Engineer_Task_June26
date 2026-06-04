"""Transcription MCP server (Phase 4).

Local MCP server (official Python SDK, ``FastMCP`` + stdio) exposing a single
speech-to-text tool backed by a local Whisper runtime. Spawned as a subprocess
by the MCP Client Manager.

Run directly for debugging:
    python -m backend.mcp_servers.transcription_mcp_server
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Optional

from mcp.server.fastmcp import FastMCP

from backend.services import speech_to_text

mcp = FastMCP("transcription-mcp-server")


@contextmanager
def _protect_stdio() -> Iterator[None]:
    """Redirect OS-level stdout (fd 1) to stderr during noisy work.

    The stdio transport uses stdout for JSON-RPC framing; ML libraries
    (faster-whisper / ctranslate2 / av) may emit stray bytes to stdout, which
    would corrupt the protocol and hang the client. We restore fd 1 before
    returning so FastMCP can serialize the response normally.
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
def transcribe_audio(audio_path: str, language: Optional[str] = None) -> dict[str, Any]:
    """Transcribe a local audio file (e.g. a WAV produced by extract_audio).

    Returns ``{text, segments, language, ...}``. Inference runs locally.
    """
    with _protect_stdio():
        return speech_to_text.transcribe_audio(audio_path, language=language)


def main() -> None:
    # Load the model on the MAIN thread before serving. FastMCP runs sync tools
    # in a worker thread, and importing/initializing the native Whisper stack
    # (ctranslate2 / onnxruntime / av) off the main thread can deadlock.
    with _protect_stdio():
        speech_to_text.warmup()
    mcp.run()


if __name__ == "__main__":
    main()
