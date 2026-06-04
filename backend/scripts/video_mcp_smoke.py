"""Phase 3 smoke test for the video MCP server + client manager.

    # Use a synthetic clip (generated automatically):
    python -m backend.scripts.video_mcp_smoke

    # Or point at a real local file:
    python -m backend.scripts.video_mcp_smoke --video "C:/path/to/sample.mp4"

Drives get_video_metadata / extract_frames / extract_audio through the
MCPClientManager over the stdio transport (real subprocess MCP server).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from backend.mcp_clients.mcp_client_manager import MCPClientManager


def _make_synthetic_video(path: Path, seconds: int = 3, fps: int = 10) -> None:
    """Write a short silent test clip (moving block) using OpenCV."""
    width, height = 320, 240
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("OpenCV could not open a VideoWriter (mp4v codec missing?)")
    total = seconds * fps
    for i in range(total):
        frame = np.full((height, width, 3), 30, dtype=np.uint8)
        x = int((i / max(total - 1, 1)) * (width - 40))
        frame[100:140, x : x + 40] = (0, 165, 255)
        writer.write(frame)
    writer.release()


async def _run(video_path: str) -> None:
    manager = MCPClientManager()

    tools = await manager.list_tools("video")
    print(f"[tools] video server exposes: {tools}")

    metadata = await manager.call_tool("video", "get_video_metadata", {"video_path": video_path})
    print("[get_video_metadata] ->")
    print(json.dumps(metadata, indent=2))

    frames = await manager.call_tool(
        "video", "extract_frames", {"video_path": video_path, "interval_seconds": 1.0}
    )
    print(f"[extract_frames] -> {frames['frame_count']} frame(s) in {frames['frames_dir']}")

    audio = await manager.call_tool("video", "extract_audio", {"video_path": video_path})
    print(f"[extract_audio] -> has_audio={audio['has_audio']} path={audio['audio_path']}")

    assert metadata["frame_count"] > 0, "expected non-zero frame count"
    assert frames["frame_count"] > 0, "expected at least one extracted frame"
    print("[done] Phase 3 video MCP smoke test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3 video MCP smoke test")
    parser.add_argument("--video", default=None, help="path to a local .mp4 (optional)")
    args = parser.parse_args()

    if args.video:
        asyncio.run(_run(args.video))
        return

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        video_path = Path(tmp) / "synthetic.mp4"
        _make_synthetic_video(video_path)
        print(f"[setup] generated synthetic clip at {video_path}")
        asyncio.run(_run(str(video_path)))


if __name__ == "__main__":
    main()
