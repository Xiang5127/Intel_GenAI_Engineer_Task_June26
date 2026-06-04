"""Summarization service (Phase 6).

Turns stored video analyses (transcript / objects / OCR / graphs) into a
*normalized* ``report_data`` + ``slide_data`` structure that the report
generator and ReportAgent consume. The downstream report layer is intentionally
agnostic about HOW the summary was produced (rules now, LLM later).

Design:
- ``Summarizer`` is the swap-in interface.
- ``RuleBasedSummarizer`` is the Phase 6 implementation (deterministic, no model).
- ``get_summarizer()`` returns the active summarizer; later phases can register
  an ``LLMSummarizer`` without touching callers, the MCP server, or ReportAgent.

# Local Ollama analysis is selected by default; the deterministic implementation
# remains the fallback and the normalized downstream contract is unchanged.
"""

from __future__ import annotations

import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional, Protocol


# --------------------------------------------------------------------------- #
# Normalized, summarizer-agnostic data structures
# --------------------------------------------------------------------------- #
@dataclass
class ReportSection:
    heading: str
    body: str = ""
    bullets: list[str] = field(default_factory=list)


@dataclass
class ReportData:
    """Normalized input for any document generator (PDF/PPTX/etc.)."""

    title: str
    subtitle: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    sections: list[ReportSection] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Slide:
    title: str
    bullets: list[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class SlideData:
    title: str
    slides: list[Slide] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SummaryBundle:
    """What every summarizer returns: normalized report + slide structures."""

    report_data: dict[str, Any]
    slide_data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {"report_data": self.report_data, "slide_data": self.slide_data}


# --------------------------------------------------------------------------- #
# Summarizer interface + implementations
# --------------------------------------------------------------------------- #
class Summarizer(Protocol):
    """Swap-in summarizer contract (RuleBased now, LLM later)."""

    name: str

    def summarize(
        self,
        analyses: dict[str, Any],
        *,
        video: Optional[dict[str, Any]] = None,
        query: Optional[str] = None,
        source_result: Optional[dict[str, Any]] = None,
        chat_messages: Optional[list[dict[str, Any]]] = None,
    ) -> SummaryBundle:
        ...


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + "..."


def _find_count(value: Any) -> Optional[dict[str, Any]]:
    if isinstance(value, dict):
        count = value.get("count")
        if isinstance(count, dict):
            return count
        for item in value.values():
            found = _find_count(item)
            if found:
                return found
    elif isinstance(value, list):
        for item in value:
            found = _find_count(item)
            if found:
                return found
    return None


class RuleBasedSummarizer:
    """Deterministic, template-based summarizer (no model)."""

    name = "rule_based"

    def summarize(
        self,
        analyses: dict[str, Any],
        *,
        video: Optional[dict[str, Any]] = None,
        query: Optional[str] = None,
        source_result: Optional[dict[str, Any]] = None,
        chat_messages: Optional[list[dict[str, Any]]] = None,
    ) -> SummaryBundle:
        video = video or {}
        is_chat_summary = bool(chat_messages) and not video
        title = "Conversation Summary" if is_chat_summary else "Video Analysis Report"
        subtitle = video.get("video_path")

        sections: list[ReportSection] = []
        slides: list[Slide] = [
            Slide(title=title, bullets=[b for b in (subtitle,) if b]),
        ]

        if is_chat_summary:
            history = [
                f"{message.get('role', 'unknown')}: {_truncate(message.get('content', ''), 500)}"
                for message in (chat_messages or [])[-20:]
            ]
            sections.append(
                ReportSection(
                    heading="Conversation",
                    body="Summary generated from recent chat history.",
                    bullets=history,
                )
            )
            slides.append(Slide(title="Conversation", bullets=history[:8]))

        # Transcript
        transcript = analyses.get("transcript") or {}
        t_text = (transcript.get("text") or "").strip()
        if t_text:
            sections.append(
                ReportSection(heading="Transcript Summary", body=_truncate(t_text, 1500))
            )
            slides.append(
                Slide(title="Transcript", bullets=[_truncate(t_text, 220)])
            )

        # Objects
        objects = analyses.get("objects") or {}
        counts = objects.get("label_counts") or {}
        if counts:
            top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
            obj_bullets = [f"{label}: {n}" for label, n in top]
            sections.append(
                ReportSection(
                    heading="Detected Objects",
                    body=f"Backend: {objects.get('backend', 'n/a')}",
                    bullets=obj_bullets,
                )
            )
            slides.append(Slide(title="Objects Detected", bullets=obj_bullets[:6]))
        elif objects:
            sections.append(
                ReportSection(
                    heading="Detected Objects",
                    body=f"No objects detected (backend: {objects.get('backend', 'n/a')}, "
                    f"available: {objects.get('detect_available')}).",
                )
            )

        # OCR
        ocr = analyses.get("ocr") or {}
        ocr_text = (ocr.get("combined_text") or "").strip()
        if ocr.get("ocr_available") and ocr_text:
            sections.append(
                ReportSection(heading="On-screen Text (OCR)", body=_truncate(ocr_text, 1200))
            )
            slides.append(Slide(title="On-screen Text", bullets=[_truncate(ocr_text, 220)]))
        elif ocr:
            sections.append(
                ReportSection(
                    heading="On-screen Text (OCR)",
                    body="OCR unavailable (no OCR backend configured)."
                    if not ocr.get("ocr_available")
                    else "No on-screen text detected.",
                )
            )

        # Graphs / charts
        graphs = analyses.get("graphs") or {}
        if graphs:
            contains = graphs.get("contains_graphs")
            body = (
                f"Charts detected in {graphs.get('graph_frame_count', 0)} of "
                f"{graphs.get('frames_analyzed', 0)} analyzed frames."
                if contains
                else "No charts/graphs detected."
            )
            sections.append(ReportSection(heading="Charts & Graphs", body=body))
            slides.append(
                Slide(
                    title="Charts & Graphs",
                    bullets=[f"Contains charts: {'yes' if contains else 'no'}"]
                    + ([f"Frames with charts: {graphs.get('graph_frame_count')}"] if contains else []),
                )
            )

        if source_result:
            count = _find_count(source_result)
            if count:
                count_bullets = [
                    f"Target: {count.get('target')}",
                    f"Maximum in one frame: {count.get('max_in_single_frame')}",
                ]
                sections.append(
                    ReportSection(heading="Requested Object Count", bullets=count_bullets)
                )
                slides.append(Slide(title="Requested Object Count", bullets=count_bullets))

        if not sections:
            sections.append(
                ReportSection(
                    heading="Summary",
                    body="No analyses available for this video yet. Run transcription "
                    "and/or visual analysis first.",
                )
            )

        metadata = {
            "generated_at": int(time.time()),
            "summarizer": self.name,
            "video_id": video.get("video_id"),
            "video_path": video.get("video_path"),
            "duration_seconds": video.get("duration_seconds"),
            "query": query,
        }

        report = ReportData(
            title=title, subtitle=subtitle, metadata=metadata, sections=sections
        )
        slide_data = SlideData(title=title, slides=slides)
        return SummaryBundle(report.to_dict(), slide_data.to_dict())


_summarizer: Optional[Summarizer] = None


def get_summarizer() -> Summarizer:
    """Return the configured local summarizer."""
    global _summarizer
    if _summarizer is None:
        if os.environ.get("ANALYSIS_BACKEND", "ollama").lower() == "rule_based":
            _summarizer = RuleBasedSummarizer()
        else:
            from backend.services.ollama_summarizer import OllamaSummarizer

            _summarizer = OllamaSummarizer()
    return _summarizer


def set_summarizer(summarizer: Optional[Summarizer]) -> None:
    """Override the active summarizer (e.g. inject LLMSummarizer in Phase 7)."""
    global _summarizer
    _summarizer = summarizer
