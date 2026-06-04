"""Local video processing service (Phase 3).

Pure, framework-agnostic functions that back the video MCP server tools. All
processing is local: OpenCV for metadata/frames, and the ffmpeg binary bundled
by ``imageio-ffmpeg`` for audio extraction (system ffmpeg is not required).

These functions return plain dicts (JSON-serializable) so they can be wrapped by
the MCP server and consumed by agents without coupling to the MCP transport.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any, Optional

import cv2

# backend/ root (this file is backend/services/video_processing.py).
BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUTS_DIR = BACKEND_DIR / "outputs"
AUDIO_DIR = OUTPUTS_DIR / "audio"
FRAMES_DIR = OUTPUTS_DIR / "frames"


class VideoProcessingError(Exception):
    """Raised when a video cannot be opened or processed."""


def _video_key(video_path: Path) -> str:
    """Stable short id for a video path (used to namespace frame outputs)."""
    digest = hashlib.sha1(str(video_path.resolve()).encode("utf-8")).hexdigest()
    return digest[:12]


def _require_existing(video_path: str) -> Path:
    path = Path(video_path)
    if not path.exists():
        raise VideoProcessingError(f"video not found: {video_path}")
    return path


def get_video_metadata(video_path: str) -> dict[str, Any]:
    """Return basic metadata: dimensions, fps, frame count, duration."""
    path = _require_existing(video_path)
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoProcessingError(f"could not open video: {video_path}")
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        cap.release()

    duration_seconds = round(frame_count / fps, 3) if fps > 0 else None
    return {
        "video_path": str(path.resolve()),
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "frame_count": frame_count,
        "duration_seconds": duration_seconds,
    }


def _ffmpeg_exe() -> str:
    """Path to a usable ffmpeg binary (bundled via imageio-ffmpeg)."""
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def extract_audio(
    video_path: str,
    output_dir: Optional[str] = None,
    sample_rate: int = 16000,
) -> dict[str, Any]:
    """Extract a mono 16 kHz WAV (whisper-friendly) from the video's audio.

    Returns ``{"audio_path": ..., "has_audio": bool, ...}``. If the video has no
    audio stream, ``has_audio`` is False and ``audio_path`` is None.
    """
    path = _require_existing(video_path)
    out_dir = Path(output_dir) if output_dir else AUDIO_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    audio_path = out_dir / f"{_video_key(path)}.wav"

    cmd = [
        _ffmpeg_exe(),
        "-y",
        "-i", str(path),
        "-vn",                       # drop video
        "-ac", "1",                  # mono
        "-ar", str(sample_rate),     # sample rate
        "-f", "wav",
        str(audio_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    if proc.returncode != 0 or not audio_path.exists() or audio_path.stat().st_size == 0:
        stderr = (proc.stderr or "").lower()
        if "does not contain any stream" in stderr or "no audio" in stderr:
            return {"audio_path": None, "has_audio": False, "sample_rate": sample_rate}
        # ffmpeg also exits non-zero when there's simply no audio stream mapped.
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return {"audio_path": None, "has_audio": False, "sample_rate": sample_rate}
        raise VideoProcessingError(f"ffmpeg failed: {proc.stderr.strip()[:500]}")

    return {
        "audio_path": str(audio_path.resolve()),
        "has_audio": True,
        "sample_rate": sample_rate,
    }


def extract_frames(
    video_path: str,
    interval_seconds: float = 5.0,
    output_dir: Optional[str] = None,
    max_frames: int = 200,
) -> dict[str, Any]:
    """Sample frames every ``interval_seconds`` and write them as JPEGs.

    Frames are written under ``outputs/frames/{video_key}/``. Returns the list of
    written frame paths plus their timestamps.
    """
    path = _require_existing(video_path)
    base_dir = Path(output_dir) if output_dir else FRAMES_DIR
    frames_dir = base_dir / _video_key(path)
    frames_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoProcessingError(f"could not open video: {video_path}")

    frames: list[dict[str, Any]] = []
    try:
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 0.0
        if fps <= 0:
            raise VideoProcessingError("could not determine video fps")
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        step = max(int(round(fps * interval_seconds)), 1)

        index = 0
        saved = 0
        while saved < max_frames:
            if frame_count > 0 and index >= frame_count:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            timestamp = round(index / fps, 3)
            frame_path = frames_dir / f"frame_{saved:04d}_t{timestamp:.2f}s.jpg"
            cv2.imwrite(str(frame_path), frame)
            frames.append({"frame_path": str(frame_path.resolve()), "timestamp": timestamp})
            saved += 1
            index += step
    finally:
        cap.release()

    return {
        "frames_dir": str(frames_dir.resolve()),
        "interval_seconds": interval_seconds,
        "frame_count": len(frames),
        "frames": frames,
    }
