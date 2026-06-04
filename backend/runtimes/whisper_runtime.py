"""Local Whisper runtime (Phase 4).

Wraps ``faster-whisper`` (CTranslate2) for fully local speech-to-text. Models are
downloaded once from the Hugging Face hub and then run locally on CPU; no audio
or text ever leaves the machine.

The runtime is intentionally abstracted behind a small interface so an
OpenVINO-based Whisper runtime can be swapped in later without touching callers.
"""

from __future__ import annotations

import os
from typing import Any, Optional, Protocol

# Imported at module load (main thread). Importing these native libs
# (ctranslate2 / onnxruntime / av) lazily inside a worker thread can deadlock,
# so we force the import to happen when this module is first imported.
from faster_whisper import WhisperModel


class SpeechToTextRuntime(Protocol):
    """Minimal interface every transcription runtime must implement."""

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict[str, Any]:
        ...


# Reasonable MVP default; override via env for accuracy/speed trade-offs.
DEFAULT_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "tiny")
DEFAULT_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


class WhisperRuntime:
    """faster-whisper based local transcription runtime."""

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL_SIZE,
        device: str = "cpu",
        compute_type: str = DEFAULT_COMPUTE_TYPE,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None  # lazily loaded

    def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def warmup(self) -> None:
        """Eagerly load the model (call on the main thread at startup)."""
        self._ensure_model()

    def transcribe(self, audio_path: str, language: Optional[str] = None) -> dict[str, Any]:
        """Transcribe a local audio file into text + timed segments."""
        model = self._ensure_model()
        segments_iter, info = model.transcribe(audio_path, language=language)

        segments: list[dict[str, Any]] = []
        texts: list[str] = []
        for seg in segments_iter:
            segments.append(
                {
                    "start": round(float(seg.start), 3),
                    "end": round(float(seg.end), 3),
                    "text": seg.text.strip(),
                }
            )
            texts.append(seg.text.strip())

        return {
            "text": " ".join(t for t in texts if t).strip(),
            "segments": segments,
            "language": getattr(info, "language", language),
            "language_probability": round(float(getattr(info, "language_probability", 0.0)), 4),
            "duration": round(float(getattr(info, "duration", 0.0)), 3),
            "model_size": self.model_size,
        }
