"""Phase 5 smoke test: VisionAgent end-to-end (OpenVINO-or-fallback).

    python -m backend.scripts.vision_smoke --video "e:/Intel Task/test_folder/test_video.mp4"

Extracts frames (video MCP) -> detect_objects / run_ocr / detect_graphs (vision
MCP) -> persists objects/ocr/graphs/visual_summary. Works with the OpenCV
fallback runtime (no detection model required); set VISION_DET_MODEL to enable
real OpenVINO object detection. Set VISION_OCR_DET_MODEL and
VISION_OCR_REC_MODEL to enable OpenVINO OCR.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import tempfile
import time
from pathlib import Path

from backend.agents.vision_agent import VisionAgent
from backend.context.context_builder import ContextBuilder
from backend.mcp_clients.mcp_client_manager import MCPClientManager
from backend.session.session_manager import SessionManager
from backend.storage.db import Database

_T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - _T0:6.1f}s] {msg}", flush=True)


def _make_video(path: Path, seconds: int = 4) -> None:
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=640x480:rate=10",
        "-pix_fmt", "yuv420p", str(path),
    ]
    subprocess.run(cmd, capture_output=True, text=True)


async def _run(db: Database, video_path: str) -> None:
    sessions = SessionManager(db)
    context_builder = ContextBuilder(sessions, db)
    mcp = MCPClientManager()
    agent = VisionAgent(mcp, db)

    session = sessions.create_session(title="Phase 5 smoke")
    sid = session["session_id"]
    video = sessions.save_video(sid, video_path)
    log(f"setup: session={sid} video={video['video_id']}")

    context = context_builder.build(sid)

    log("run: vision analysis (spawns video + vision MCP servers)")
    result = await agent.handle("ANALYZE_VISUAL", {"interval_seconds": 2.0}, context)
    log(f"run done: success={result.success}")
    log(f"  summary={result.summary!r}")
    assert result.success, f"vision analysis failed: {result.error}"

    obj = result.data["objects"]
    log(f"  objects backend={obj['backend']} detect_available={obj['detect_available']} "
        f"labels={obj['label_counts']}")
    if obj.get("configuration_errors"):
        log(f"  object/model notes={obj['configuration_errors']}")
    ocr = result.data["ocr"]
    log(f"  ocr backend={ocr['backend']} available={ocr['ocr_available']} "
        f"chars={len(ocr.get('combined_text') or '')}")
    if ocr.get("configuration_errors"):
        log(f"  ocr/model notes={ocr['configuration_errors']}")
    log(f"  graphs contains={result.data['graphs']['contains_graphs']} "
        f"({result.data['graphs']['graph_frame_count']}/{result.data['graphs']['frames_analyzed']})")

    for t in ("objects", "ocr", "graphs", "visual_summary"):
        assert db.get_latest_analysis(video["video_id"], t) is not None, f"{t} not persisted"
    log("persist: objects/ocr/graphs/visual_summary stored")

    log("DONE: Phase 5 vision smoke test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 5 vision smoke test")
    parser.add_argument("--video", default=None, help="path to a local .mp4 (optional)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(Path(tmp) / "phase5.db")
        db.initialize()
        try:
            if args.video:
                log(f"using provided video: {args.video}")
                asyncio.run(_run(db, args.video))
            else:
                vp = Path(tmp) / "synthetic.mp4"
                _make_video(vp)
                log(f"generated synthetic clip at {vp}")
                asyncio.run(_run(db, str(vp)))
        finally:
            db.close()


if __name__ == "__main__":
    main()
