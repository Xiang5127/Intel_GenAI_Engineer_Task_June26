"""SummaryAgent (Phase 6).

Reads the stored analyses for the current video (transcript / objects / OCR /
graphs) and produces a *normalized* ``report_data`` + ``slide_data`` bundle via
the active :class:`Summarizer` (rule-based in Phase 6, LLM later). The agent is
summarizer-agnostic; swapping in an LLM summarizer requires no change here.

It does not call MCP tools (summarization is local/CPU-light); it only reads/
writes storage and delegates to the summarization service.
"""

from __future__ import annotations

import json
from typing import Any

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.services import summarization

ANALYSIS_TYPE = "summary"
_SOURCE_TYPES = ("transcript", "objects", "ocr", "graphs")


class SummaryAgent(BaseAgent):
    name = "summary_agent"

    async def handle(
        self,
        intent: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        video = self._current_video(context)
        video_id = (video or {}).get("video_id")
        if not video_id:
            return self._fail(intent, "no video selected to summarize")

        analyses = self._load_analyses(video_id)
        if not any(analyses.values()):
            return self._fail(
                intent,
                "no analyses found; run transcription and/or visual analysis first",
            )

        summarizer = summarization.get_summarizer()
        bundle = summarizer.summarize(analyses, video=video, query=inputs.get("query"))

        self.db.save_video_analysis(video_id, ANALYSIS_TYPE, json.dumps(bundle.to_dict()))

        n_sections = len(bundle.report_data.get("sections", []))
        n_slides = len(bundle.slide_data.get("slides", []))
        summary = (
            f"Summary built by '{summarizer.name}' summarizer: "
            f"{n_sections} report section(s), {n_slides} slide(s)."
        )
        return self._ok(intent, summary, bundle.to_dict())

    def _load_analyses(self, video_id: str) -> dict[str, Any]:
        analyses: dict[str, Any] = {}
        for t in _SOURCE_TYPES:
            row = self.db.get_latest_analysis(video_id, t)
            analyses[t] = json.loads(row["result_json"]) if row else None
        return analyses
