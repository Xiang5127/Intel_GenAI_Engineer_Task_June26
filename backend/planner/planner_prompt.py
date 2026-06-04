"""Planner prompt builder (Phase 7).

Constructs the instruction a planner LLM receives: it lists the allowed agents
and intents, embeds the compact session context, and demands a JSON-only plan
matching ``plan_schema``. The stub planner ignores the prompt text, but a real
LLM adapter (Phase 7+) feeds this string to the model.

# TODO(Phase 7): feed this prompt to a local LLM adapter and parse its JSON output.
"""

from __future__ import annotations

import json
from typing import Any

from backend.planner.plan_schema import Agent, Intent

_INTENT_LINES = "\n".join(f"- {i.value}" for i in Intent)
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


def build_planner_prompt(user_query: str, context: dict[str, Any]) -> str:
    """Return the full planner prompt for ``user_query`` given ``context``."""
    has_video = bool(context.get("current_video"))
    compact_context = {
        "has_selected_video": has_video,
        "current_video": context.get("current_video"),
        "pending_clarification": context.get("pending_clarification"),
        "recent_messages": context.get("recent_messages", [])[-5:],
        "generated_files": context.get("generated_files", []),
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

Schema example:
{_SCHEMA_EXAMPLE}

Session context (JSON):
{json.dumps(compact_context, indent=2)}

User request:
{user_query}

JSON plan:"""
