"""Speech-to-text service (Phase 4).

Thin, transport-agnostic wrapper around a local ``SpeechToTextRuntime`` that
backs the transcription MCP tool. The runtime is created lazily and cached at
module level so the model is loaded once per server process.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from backend.runtimes.whisper_runtime import WhisperRuntime

_runtime: Optional[WhisperRuntime] = None


class SpeechToTextError(Exception):
    """Raised when audio cannot be transcribed."""


def _get_runtime() -> WhisperRuntime:
    global _runtime
    if _runtime is None:
        _runtime = WhisperRuntime()
    return _runtime


def warmup() -> None:
    """Eagerly load the model on the current (ideally main) thread."""
    _get_runtime().warmup()


def transcribe_audio(audio_path: str, language: Optional[str] = None) -> dict[str, Any]:
    """Transcribe a local audio file. Returns text + segments + metadata."""
    path = Path(audio_path)
    if not path.exists():
        raise SpeechToTextError(f"audio not found: {audio_path}")
    if path.stat().st_size == 0:
        raise SpeechToTextError(f"audio file is empty: {audio_path}")
    return _get_runtime().transcribe(str(path), language=language)
