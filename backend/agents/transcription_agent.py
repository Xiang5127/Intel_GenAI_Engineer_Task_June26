"""TranscriptionAgent (Phase 4).

Orchestrates local transcription end-to-end:
1. Resolve the current video from context (or an explicit ``video_path`` input).
2. Reuse a cached transcript from ``video_analysis`` unless ``force`` is set.
3. Call the video MCP ``extract_audio`` tool to produce a WAV.
4. Call the transcription MCP ``transcribe_audio`` tool (local Whisper).
5. Persist the transcript into ``video_analysis`` and return a summary.

It uses only MCP tools + storage; no model code lives here.
"""

from __future__ import annotations

import json
from typing import Any

from backend.agents.base_agent import AgentResult, BaseAgent

ANALYSIS_TYPE = "transcript"
_SUMMARY_CHARS = 280


class TranscriptionAgent(BaseAgent):
    name = "transcription_agent"

    async def handle(
        self,
        intent: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        video = self._current_video(context)
        video_path = inputs.get("video_path") or (video or {}).get("video_path")
        video_id = (video or {}).get("video_id")

        if not video_path:
            return self._fail(intent, "no video selected to transcribe")

        # 1. Reuse cached transcript unless forced.
        if video_id and not inputs.get("force"):
            cached = self.db.get_latest_analysis(video_id, ANALYSIS_TYPE)
            if cached:
                transcript = json.loads(cached["result_json"])
                return self._ok(
                    intent,
                    self._summarize(transcript, cached=True),
                    {"transcript": transcript, "cached": True},
                )

        # 2. Extract audio via the video MCP server.
        try:
            audio = await self.mcp.call_tool(
                "video", "extract_audio", {"video_path": video_path}
            )
        except Exception as exc:  # noqa: BLE001 - surface tool errors to the user
            return self._fail(intent, f"audio extraction failed: {exc}")

        if not audio.get("has_audio") or not audio.get("audio_path"):
            return self._fail(intent, "video has no audio track to transcribe")

        # 3. Transcribe via the transcription MCP server.
        try:
            transcript = await self.mcp.call_tool(
                "transcription",
                "transcribe_audio",
                {"audio_path": audio["audio_path"], "language": inputs.get("language")},
            )
        except Exception as exc:  # noqa: BLE001
            return self._fail(intent, f"transcription failed: {exc}")

        # 4. Persist.
        if video_id:
            self.db.save_video_analysis(video_id, ANALYSIS_TYPE, json.dumps(transcript))

        return self._ok(
            intent,
            self._summarize(transcript, cached=False),
            {"transcript": transcript, "cached": False, "audio_path": audio["audio_path"]},
        )

    @staticmethod
    def _summarize(transcript: dict[str, Any], cached: bool) -> str:
        text = (transcript.get("text") or "").strip()
        prefix = "Transcript (cached)" if cached else "Transcript"
        if not text:
            return f"{prefix}: (no speech detected)"
        snippet = text[:_SUMMARY_CHARS]
        if len(text) > _SUMMARY_CHARS:
            snippet += "..."
        return f"{prefix}: {snippet}"
