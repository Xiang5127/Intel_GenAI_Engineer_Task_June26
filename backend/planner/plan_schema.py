"""Plan schema (Phase 7).

Pydantic models + enums defining the JSON execution plan the planner produces and
the validator/executor consume. Mirrors ``03_PLAN_SCHEMA.md``.

The planner (LLM or stub) outputs JSON shaped like::

    {
      "confidence": 0.91,
      "steps": [
        {"step_id": "step_1", "intent": "COUNT_OBJECTS", "agent": "vision_agent",
         "inputs": {"target": "animals"}, "depends_on": []}
      ],
      "clarification_question": null
    }
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Agent(str, Enum):
    TRANSCRIPTION = "transcription_agent"
    VISION = "vision_agent"
    SUMMARY = "summary_agent"
    REPORT = "report_agent"
    CLARIFICATION = "clarification_agent"


class Intent(str, Enum):
    TRANSCRIBE_VIDEO = "TRANSCRIBE_VIDEO"
    SUMMARIZE_VIDEO = "SUMMARIZE_VIDEO"
    ANALYZE_OBJECTS = "ANALYZE_OBJECTS"
    COUNT_OBJECTS = "COUNT_OBJECTS"
    DETECT_GRAPHS = "DETECT_GRAPHS"
    ANALYZE_OCR = "ANALYZE_OCR"
    SUMMARIZE_CHAT_HISTORY = "SUMMARIZE_CHAT_HISTORY"
    GENERATE_PDF = "GENERATE_PDF"
    GENERATE_PPTX = "GENERATE_PPTX"
    CLARIFY = "CLARIFY"


# Which agent handles each intent.
INTENT_TO_AGENT: dict[Intent, Agent] = {
    Intent.TRANSCRIBE_VIDEO: Agent.TRANSCRIPTION,
    Intent.SUMMARIZE_VIDEO: Agent.SUMMARY,
    Intent.SUMMARIZE_CHAT_HISTORY: Agent.SUMMARY,
    Intent.ANALYZE_OBJECTS: Agent.VISION,
    Intent.COUNT_OBJECTS: Agent.VISION,
    Intent.DETECT_GRAPHS: Agent.VISION,
    Intent.ANALYZE_OCR: Agent.VISION,
    Intent.GENERATE_PDF: Agent.REPORT,
    Intent.GENERATE_PPTX: Agent.REPORT,
    Intent.CLARIFY: Agent.CLARIFICATION,
}

# Intents that require a selected video to run.
VIDEO_REQUIRED_INTENTS: frozenset[Intent] = frozenset(
    {
        Intent.TRANSCRIBE_VIDEO,
        Intent.SUMMARIZE_VIDEO,
        Intent.ANALYZE_OBJECTS,
        Intent.COUNT_OBJECTS,
        Intent.DETECT_GRAPHS,
        Intent.ANALYZE_OCR,
    }
)

REPORT_INTENTS: frozenset[Intent] = frozenset({Intent.GENERATE_PDF, Intent.GENERATE_PPTX})

# Minimum confidence to execute a non-clarifying plan.
MIN_CONFIDENCE = 0.7


class PlanStep(BaseModel):
    step_id: str
    intent: Intent
    agent: Agent
    inputs: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    optional: bool = False


class Plan(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    steps: list[PlanStep] = Field(default_factory=list)
    clarification_question: Optional[str] = None

    def is_clarification(self) -> bool:
        return any(s.intent == Intent.CLARIFY for s in self.steps)
