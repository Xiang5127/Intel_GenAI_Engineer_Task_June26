"""Video processing MCP server (Phase 3).

A real local MCP server built on the official Python MCP SDK (``FastMCP``),
exposing video tools over the stdio transport. It is spawned as a subprocess by
the MCP Client Manager and consumed by agents.

Tools:
- ``get_video_metadata(video_path)``
- ``extract_audio(video_path, sample_rate=16000)``
- ``extract_frames(video_path, interval_seconds=5)``

Run directly for debugging:
    python -m backend.mcp_servers.video_mcp_server
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from backend.services import video_processing

mcp = FastMCP("video-mcp-server")


@mcp.tool()
def get_video_metadata(video_path: str) -> dict[str, Any]:
    """Return basic metadata (dimensions, fps, frame count, duration) for a local video."""
    return video_processing.get_video_metadata(video_path)


@mcp.tool()
def extract_audio(video_path: str, sample_rate: int = 16000) -> dict[str, Any]:
    """Extract a mono WAV track from the video for downstream transcription.

    Returns ``has_audio=False`` (and ``audio_path=None``) if the video has no
    audio stream.
    """
    return video_processing.extract_audio(video_path, sample_rate=sample_rate)


@mcp.tool()
def extract_frames(
    video_path: str, interval_seconds: float = 5.0, max_frames: int = 200
) -> dict[str, Any]:
    """Sample frames every ``interval_seconds`` and return their saved paths + timestamps."""
    return video_processing.extract_frames(
        video_path, interval_seconds=interval_seconds, max_frames=max_frames
    )


def main() -> None:
    # Default transport is stdio; the MCP Client Manager spawns this process.
    mcp.run()


if __name__ == "__main__":
    main()
