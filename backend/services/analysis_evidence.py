"""Build bounded, model-safe evidence from agent and chat results."""

from __future__ import annotations

import json
from typing import Any, Iterable, Optional

MAX_TRANSCRIPT_CHARS = 6000
MAX_OCR_CHARS = 2500
MAX_SOURCE_CHARS = 5000
MAX_CHAT_MESSAGES = 12
MAX_CHAT_MESSAGE_CHARS = 600


def _bounded(value: Any, limit: int) -> str:
    text = str(value or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _dedupe_lines(text: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for raw in text.splitlines():
        line = " ".join(raw.split())
        key = line.casefold()
        if line and key not in seen:
            seen.add(key)
            lines.append(line)
    return "\n".join(lines)


def _compact_source(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        return _bounded(value, 500)
    if isinstance(value, dict):
        return {
            str(key): _compact_source(item, depth=depth + 1)
            for key, item in list(value.items())[:20]
            if key not in {"frame_paths", "frames", "segments", "audio_path"}
        }
    if isinstance(value, list):
        return [_compact_source(item, depth=depth + 1) for item in value[:12]]
    if isinstance(value, str):
        return _bounded(value, 1000)
    return value


def evidence_types(evidence: dict[str, Any]) -> list[str]:
    return [
        key
        for key in ("transcript", "ocr", "objects", "graphs", "source_result", "chat_history")
        if evidence.get(key)
    ]


def build_analysis_evidence(
    analyses: Optional[dict[str, Any]] = None,
    *,
    source_result: Optional[dict[str, Any]] = None,
    chat_messages: Optional[Iterable[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Return compact evidence suitable for a local model prompt.

    Evidence is data, not instructions. Large per-frame and per-segment payloads
    are intentionally omitted.
    """
    analyses = analyses or {}
    evidence: dict[str, Any] = {}

    transcript = analyses.get("transcript") or {}
    transcript_text = _bounded(transcript.get("text"), MAX_TRANSCRIPT_CHARS)
    if transcript_text:
        evidence["transcript"] = {
            "text": transcript_text,
            "language": transcript.get("language"),
        }

    ocr = analyses.get("ocr") or {}
    ocr_text = _bounded(_dedupe_lines(ocr.get("combined_text") or ""), MAX_OCR_CHARS)
    if ocr_text or ocr:
        evidence["ocr"] = {
            "text": ocr_text,
            "available": ocr.get("ocr_available"),
            "backend": ocr.get("backend"),
        }

    objects = analyses.get("objects") or {}
    if objects:
        counts = objects.get("label_counts") or {}
        evidence["objects"] = {
            "label_counts": dict(list(counts.items())[:50]),
            "frames_analyzed": objects.get("frames_analyzed"),
            "available": objects.get("detect_available"),
            "backend": objects.get("backend"),
        }

    graphs = analyses.get("graphs") or {}
    if graphs:
        evidence["graphs"] = {
            "contains_graphs": graphs.get("contains_graphs"),
            "graph_frame_count": graphs.get("graph_frame_count"),
            "frames_analyzed": graphs.get("frames_analyzed"),
        }

    if source_result:
        compact = _compact_source(source_result)
        serialized = json.dumps(compact, ensure_ascii=True)
        evidence["source_result"] = (
            compact
            if len(serialized) <= MAX_SOURCE_CHARS
            else {"truncated_json": _bounded(serialized, MAX_SOURCE_CHARS)}
        )

    if chat_messages:
        evidence["chat_history"] = [
            {
                "role": str(message.get("role", "unknown")),
                "content": _bounded(message.get("content"), MAX_CHAT_MESSAGE_CHARS),
            }
            for message in list(chat_messages)[-MAX_CHAT_MESSAGES:]
        ]

    return evidence
