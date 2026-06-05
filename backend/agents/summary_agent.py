"""SummaryAgent (Phase 6).

Reads stored video evidence or chat history and produces a normalized
``report_data`` + ``slide_data`` bundle via the active :class:`Summarizer`.
The default summarizer uses local Ollama with a deterministic fallback.

It does not call MCP tools; it only reads/writes storage and delegates to the
local summarization service.
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
        is_chat_summary = intent == "SUMMARIZE_CHAT_HISTORY"
        video = self._current_video(context)
        video_id = (video or {}).get("video_id")
        if not video_id and not is_chat_summary:
            return self._fail(intent, "no video selected to summarize")

        analyses = self._load_analyses(video_id) if video_id else {}
        session_id = context.get("session_id")
        chat_messages = (
            self.db.get_recent_messages(session_id, 20)
            if is_chat_summary and session_id
            else context.get("recent_messages", []) if is_chat_summary else None
        )
        if not any(analyses.values()) and not chat_messages:
            return self._fail(
                intent,
                "no evidence found to summarize",
            )

        summarizer = summarization.get_summarizer()
        source_result = inputs.get("source_result")
        dependency_results = inputs.get("dependency_results") or {}
        if dependency_results:
            source_result = {
                "primary": source_result or {},
                "dependencies": dependency_results,
            }
        bundle = summarizer.summarize(
            analyses,
            video=None if is_chat_summary else video,
            query=inputs.get("query"),
            source_result=source_result,
            chat_messages=chat_messages,
        )

        if video_id and not is_chat_summary:
            self.db.save_video_analysis(video_id, ANALYSIS_TYPE, json.dumps(bundle.to_dict()))
        if session_id:
            self.db.save_content_bundle(
                session_id,
                "chat_summary" if is_chat_summary else "video_summary",
                json.dumps(bundle.to_dict()),
                video_id=None if is_chat_summary else video_id,
                query=inputs.get("query"),
            )

        n_sections = len(bundle.report_data.get("sections", []))
        n_slides = len(bundle.slide_data.get("slides", []))
        summary = f"Summary ready: {n_sections} section(s), {n_slides} slide(s)."
        return self._ok(intent, summary, bundle.to_dict())

    def _load_analyses(self, video_id: str) -> dict[str, Any]:
        analyses: dict[str, Any] = {}
        for t in _SOURCE_TYPES:
            row = self.db.get_latest_analysis(video_id, t)
            analyses[t] = json.loads(row["result_json"]) if row else None
        return analyses
