"""Phase 4 smoke test: TranscriptionAgent end-to-end (local Whisper).

    python -m backend.scripts.transcription_smoke
    python -m backend.scripts.transcription_smoke --video "C:/path/to/sample.mp4"

Generates a short synthetic clip WITH an audio track (so extract_audio succeeds),
then runs TranscriptionAgent: extract_audio (video MCP) -> transcribe_audio
(transcription MCP, local Whisper) -> persist to video_analysis -> cache reuse.

Note: the first run downloads the Whisper "tiny" model from the HF hub (one-time);
inference itself is fully local.
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from backend.agents.transcription_agent import TranscriptionAgent
from backend.context.context_builder import ContextBuilder
from backend.mcp_clients.mcp_client_manager import MCPClientManager
from backend.session.session_manager import SessionManager
from backend.storage.db import Database

_T0 = time.time()


def log(msg: str) -> None:
    """Timestamped, flushed progress line."""
    print(f"[{time.time() - _T0:6.1f}s] {msg}", flush=True)


def _make_video_with_audio(path: Path, seconds: int = 3) -> None:
    """Use the bundled ffmpeg to synthesize a clip with video + sine audio."""
    import imageio_ffmpeg

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=10",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-shortest", "-pix_fmt", "yuv420p",
        str(path),
    ]
    log("generating synthetic clip with audio via bundled ffmpeg...")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not path.exists():
        raise RuntimeError(f"ffmpeg failed to create test clip: {proc.stderr[:500]}")
    log(f"clip ready ({path.stat().st_size} bytes)")


async def _run(db: Database, video_path: str) -> None:
    sessions = SessionManager(db)
    context_builder = ContextBuilder(sessions, db)
    mcp = MCPClientManager()
    agent = TranscriptionAgent(mcp, db)

    session = sessions.create_session(title="Phase 4 smoke")
    sid = session["session_id"]
    video = sessions.save_video(sid, video_path)
    log(f"setup: session={sid} video={video['video_id']}")

    context = context_builder.build(sid)

    # Warm up the model in THIS process so the one-time HF download shows its
    # progress bars in the foreground. The MCP subprocess then reuses the cache.
    log("warmup: loading Whisper model in-process (HF download progress below if first run)...")
    from backend.runtimes.whisper_runtime import WhisperRuntime

    WhisperRuntime()._ensure_model()
    log("warmup: model ready (cached locally)")

    log("run 1: starting transcription (spawns video + transcription MCP servers)")
    result = await agent.handle("TRANSCRIBE_VIDEO", {}, context)
    log(f"run 1 done: success={result.success} cached={result.data.get('cached')}")
    log(f"       summary={result.summary!r}")
    assert result.success, f"transcription failed: {result.error}"
    assert "transcript" in result.data and "text" in result.data["transcript"]

    saved = db.get_latest_analysis(video["video_id"], "transcript")
    assert saved is not None, "transcript not persisted to video_analysis"
    log("persist: transcript stored in video_analysis")

    log("run 2: transcribing again (expect cache hit, no model work)")
    result2 = await agent.handle("TRANSCRIBE_VIDEO", {}, context)
    assert result2.data.get("cached") is True, "expected cached transcript on 2nd run"
    log("run 2 done: cache hit confirmed")

    log("DONE: Phase 4 transcription smoke test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 4 transcription smoke test")
    parser.add_argument("--video", default=None, help="path to a local .mp4 (optional)")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(Path(tmp) / "phase4.db")
        db.initialize()
        try:
            if args.video:
                log(f"using provided video: {args.video}")
                asyncio.run(_run(db, args.video))
            else:
                video_path = Path(tmp) / "with_audio.mp4"
                _make_video_with_audio(video_path)
                asyncio.run(_run(db, str(video_path)))
        finally:
            db.close()


if __name__ == "__main__":
    main()
