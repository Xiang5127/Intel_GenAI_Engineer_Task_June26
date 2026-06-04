"""Planner service (Phase 7).

Produces a raw JSON execution plan from a user query + context. The actual
"thinking" lives behind a swappable :class:`PlannerModel` adapter:

- ``HeuristicPlannerModel`` (default): a deterministic, keyword-based stub that
  emits valid plans for the supported intents. No LLM, fully offline.
- A real local LLM adapter can be dropped in later via ``set_planner_model``
  without changing the validator, executor, or gRPC layer.

``generate_plan(user_query, context) -> str`` returns raw JSON (string), exactly
as an LLM would, so the validator path is identical for stub and LLM.

# TODO(Phase 7): implement LLMPlannerModel(PlannerModel) using the local model;
#                feed build_planner_prompt() and parse the JSON response.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Protocol

from backend.planner.planner_prompt import build_planner_prompt

# Words that hint at a specific object-count target ("how many X").
_COUNT_RE = re.compile(r"how many\s+([a-z][a-z\s]*?)(?:\s+(?:are|is|in|on|appear)|\?|$)", re.I)


class PlannerModel(Protocol):
    """Swap-in planner contract; returns a raw JSON plan string."""

    name: str

    def generate(self, prompt: str, user_query: str, context: dict[str, Any]) -> str:
        ...


def _step(step_id: str, intent: str, agent: str, inputs: dict[str, Any], depends_on: list[str]) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "intent": intent,
        "agent": agent,
        "inputs": inputs,
        "depends_on": depends_on,
    }


def _clarify(question: str, confidence: float = 0.45) -> dict[str, Any]:
    return {
        "confidence": confidence,
        "steps": [_step("step_1", "CLARIFY", "clarification_agent", {"question": question}, [])],
        "clarification_question": question,
    }


class HeuristicPlannerModel:
    """Deterministic keyword planner (stand-in for an LLM)."""

    name = "heuristic_stub"

    def generate(self, prompt: str, user_query: str, context: dict[str, Any]) -> str:
        q = (user_query or "").lower().strip()
        has_video = bool(context.get("current_video"))

        if not q:
            return json.dumps(_clarify("What would you like me to do with the video?"))

        # Determine the primary analysis intent.
        steps: list[dict[str, Any]] = []
        primary: Optional[dict[str, Any]] = None

        if "transcri" in q:
            primary = _step("step_1", "TRANSCRIBE_VIDEO", "transcription_agent", {}, [])
        elif "how many" in q or "count" in q:
            target = self._extract_target(q)
            primary = _step("step_1", "COUNT_OBJECTS", "vision_agent", {"target": target}, [])
        elif any(k in q for k in ("graph", "chart", "plot")):
            primary = _step("step_1", "DETECT_GRAPHS", "vision_agent", {}, [])
        elif any(k in q for k in ("ocr", "text on screen", "on-screen text", "read text", "written")):
            primary = _step("step_1", "ANALYZE_OCR", "vision_agent", {}, [])
        elif any(k in q for k in ("object", "what is shown", "what's shown", "what do you see", "detect")):
            primary = _step("step_1", "ANALYZE_OBJECTS", "vision_agent", {}, [])
        elif "summar" in q:
            primary = _step("step_1", "SUMMARIZE_VIDEO", "summary_agent", {}, [])

        # Determine requested export format(s).
        wants_pdf = "pdf" in q
        wants_pptx = any(k in q for k in ("pptx", "powerpoint", "power point", "slide", "presentation"))
        wants_report = "report" in q or "export" in q or "generate" in q

        if primary is None:
            # Only an export/report was requested.
            if wants_pdf and not wants_pptx:
                primary = None  # report-only handled below
            elif wants_pptx and not wants_pdf:
                primary = None
            elif wants_report and not (wants_pdf or wants_pptx):
                # Ambiguous "make a report" -> clarify format.
                return json.dumps(_clarify("Do you want a PDF report or a PowerPoint presentation?"))
            else:
                return json.dumps(
                    _clarify("I can transcribe, analyze objects/OCR/graphs, summarize, or "
                             "generate a PDF/PPTX. What would you like?")
                )

        if primary is not None:
            steps.append(primary)

        # Append report step if an export format was requested.
        if wants_pdf or wants_pptx:
            dep = [primary["step_id"]] if primary is not None else []
            src = {"source_step": primary["step_id"]} if primary is not None else {}
            next_id = f"step_{len(steps) + 1}"
            if wants_pdf:
                steps.append(_step(next_id, "GENERATE_PDF", "report_agent", {"title": "Video Report", **src}, dep))
            if wants_pptx:
                nid = f"step_{len(steps) + 1}"
                steps.append(_step(nid, "GENERATE_PPTX", "report_agent", {"title": "Video Report", **src}, dep))

        if not steps:
            return json.dumps(_clarify("Could you clarify what you'd like me to do?"))

        confidence = 0.9 if has_video or not _needs_video(steps) else 0.88
        return json.dumps(
            {"confidence": confidence, "steps": steps, "clarification_question": None}
        )

    @staticmethod
    def _extract_target(q: str) -> str:
        m = _COUNT_RE.search(q)
        if m:
            return m.group(1).strip()
        return "object"


def _needs_video(steps: list[dict[str, Any]]) -> bool:
    vid = {"TRANSCRIBE_VIDEO", "SUMMARIZE_VIDEO", "ANALYZE_OBJECTS", "COUNT_OBJECTS",
           "DETECT_GRAPHS", "ANALYZE_OCR"}
    return any(s["intent"] in vid for s in steps)


class PlannerService:
    """Builds the prompt and delegates plan generation to a PlannerModel."""

    def __init__(self, model: Optional[PlannerModel] = None) -> None:
        self._model = model or HeuristicPlannerModel()

    @property
    def model_name(self) -> str:
        return self._model.name

    def set_model(self, model: PlannerModel) -> None:
        self._model = model

    def generate_plan(self, user_query: str, context: dict[str, Any]) -> str:
        """Return a raw JSON plan string for ``user_query``."""
        prompt = build_planner_prompt(user_query, context)
        return self._model.generate(prompt, user_query, context)
