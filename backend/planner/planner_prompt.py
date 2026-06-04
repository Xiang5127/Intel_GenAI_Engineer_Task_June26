"""Planner prompt builder (Phase 7).

Constructs the instruction a planner LLM receives: it lists the allowed agents
and intents, embeds the compact session context, and demands a JSON-only plan
matching ``plan_schema``. The stub planner ignores the prompt text, but a real
LLM adapter (Phase 7+) feeds this string to the model.

Consumed by ``OllamaPlannerModel`` (local LLM); the heuristic stub ignores it.
"""

from __future__ import annotations

import json
from typing import Any

from backend.planner.plan_schema import Agent, Intent

_INTENT_DESCRIPTIONS = {
    Intent.TRANSCRIBE_VIDEO: "transcribe the spoken audio of the video",
    Intent.SUMMARIZE_VIDEO: "produce a summary of the video content",
    Intent.ANALYZE_OBJECTS: "detect and list the objects shown in the video",
    Intent.COUNT_OBJECTS: "count how many of a SPECIFIC object appear; use this for "
    "\"how many X\" / \"count the X\" questions and put X in inputs.target",
    Intent.DETECT_GRAPHS: "detect charts/graphs/plots in the video",
    Intent.ANALYZE_OCR: "read on-screen / written text from the video",
    Intent.SUMMARIZE_CHAT_HISTORY: "summarize the conversation so far",
    Intent.GENERATE_PDF: "create a PDF report (report_agent)",
    Intent.GENERATE_PPTX: "create a PowerPoint presentation (report_agent)",
    Intent.CLARIFY: "ask the user a clarifying question when the request is ambiguous",
}
_INTENT_LINES = "\n".join(f"- {i.value}: {_INTENT_DESCRIPTIONS[i]}" for i in Intent)
_AGENT_LINES = "\n".join(f"- {a.value}" for a in Agent)

_SCHEMA_EXAMPLE = """{
  "confidence": 0.92,
  "steps": [
    {"step_id": "step_1", "intent": "COUNT_OBJECTS", "agent": "vision_agent",
     "inputs": {"target": "animals"}, "depends_on": []},
    {"step_id": "step_2", "intent": "GENERATE_PDF", "agent": "report_agent",
     "inputs": {"title": "Animal Count Report", "source_step": "step_1"},
     "depends_on": ["step_1"]}
  ],
  "clarification_question": null
}"""

_MORE_EXAMPLES = """More examples:

User: "Transcribe the video"
{"confidence": 0.95, "steps": [{"step_id": "step_1", "intent": "TRANSCRIBE_VIDEO",
 "agent": "transcription_agent", "inputs": {}, "depends_on": []}],
 "clarification_question": null}

User: "Make a report" (no format given)
{"confidence": 0.45, "steps": [{"step_id": "step_1", "intent": "CLARIFY",
 "agent": "clarification_agent",
 "inputs": {"question": "Do you want a PDF report or a PowerPoint presentation?"},
 "depends_on": []}],
 "clarification_question": "Do you want a PDF report or a PowerPoint presentation?"}"""


def build_planner_prompt(user_query: str, context: dict[str, Any]) -> str:
    """Return the full planner prompt for ``user_query`` given ``context``."""
    has_video = bool(context.get("current_video"))
    compact_context = {
        "has_selected_video": has_video,
        "current_video": context.get("current_video"),
        "pending_clarification": context.get("pending_clarification"),
        "recent_messages": context.get("recent_messages", [])[-5:],
        "generated_files": context.get("generated_files", []),
        "available_analyses": context.get("available_analyses", {}),
    }

    return f"""You are a planning module for a local video-analysis assistant.
Convert the user's request into a JSON execution plan. Output JSON ONLY, no prose.

Allowed agents:
{_AGENT_LINES}

Allowed intents:
{_INTENT_LINES}

Rules:
- Output a single JSON object matching the schema below.
- confidence is 0.0-1.0. Use >= 0.7 when you are confident.
- If the request is ambiguous or under-specified, emit a single CLARIFY step with
  a clarification_question and confidence < 0.7.
- Video-required intents (transcribe, summarize video, object/ocr/graph analysis)
  need a selected video.
- For multi-step requests, use depends_on and reference prior steps via
  inputs.source_step.
- For general questions about the selected video's content, use SUMMARIZE_VIDEO
  and put the user's question in inputs.query.
- Use SUMMARIZE_CHAT_HISTORY only when the user explicitly asks about the
  conversation, discussion, or chat history rather than the video.
- Use the single most specific intent for the analysis; do NOT add redundant
  steps (e.g. for "how many animals" use COUNT_OBJECTS alone, not ANALYZE_OBJECTS
  as well).

Schema example:
{_SCHEMA_EXAMPLE}

{_MORE_EXAMPLES}

Output rules: respond with ONE JSON object only. No markdown, no code fences, no
explanation. Every step's "agent" must match its "intent".

Session context (JSON):
{json.dumps(compact_context, indent=2)}

User request:
{user_query}

JSON plan:"""
