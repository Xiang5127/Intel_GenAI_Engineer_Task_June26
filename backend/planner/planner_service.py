"""Planner service (Phase 7).

Produces a raw JSON execution plan from a user query + context. The actual
"thinking" lives behind a swappable :class:`PlannerModel` adapter:

- ``HeuristicPlannerModel``: a deterministic, keyword-based fallback that
  emits valid plans for the supported intents. No LLM, fully offline.
- A real local LLM adapter can be dropped in later via ``set_planner_model``
  without changing the validator, executor, or gRPC layer.

``generate_plan(user_query, context) -> str`` returns raw JSON (string), exactly
as an LLM would, so the validator path is identical for stub and LLM.

The local LLM adapter (``OllamaPlannerModel``) is the default primary; the
heuristic stub remains as an automatic offline fallback.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional, Protocol

from backend.planner.planner_prompt import build_planner_prompt
from backend.planner.workflow_router import route_known_workflow

_log = logging.getLogger(__name__)

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
        elif "summar" in q and any(k in q for k in ("chat", "conversation", "discussion")):
            primary = _step(
                "step_1", "SUMMARIZE_CHAT_HISTORY", "summary_agent", {"query": user_query}, []
            )
        elif "summar" in q:
            primary = _step(
                "step_1", "SUMMARIZE_VIDEO", "summary_agent", {"query": user_query}, []
            )

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
                if _looks_like_video_question(q, has_video):
                    primary = _step(
                        "step_1", "SUMMARIZE_VIDEO", "summary_agent", {"query": user_query}, []
                    )
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


def _looks_like_video_question(query: str, has_video: bool) -> bool:
    if not has_video:
        return False
    return any(
        marker in query
        for marker in (
            "what ",
            "why ",
            "how ",
            "explain",
            "tell me",
            "main point",
            "topic",
            "happen",
            "about",
            "key point",
        )
    )


def _default_model() -> PlannerModel:
    """Pick the primary planner model from env (default: Ollama LLM).

    ``PLANNER_BACKEND=heuristic`` forces the offline stub; anything else (default)
    uses the local Ollama LLM, which itself falls back to the heuristic if the
    server is unreachable (handled by PlannerService).
    """
    backend = os.environ.get("PLANNER_BACKEND", "ollama").lower()
    if backend == "heuristic":
        return HeuristicPlannerModel()
    # Imported lazily so the heuristic path has no hard dependency on the adapter.
    from backend.planner.ollama_planner_model import OllamaPlannerModel

    return OllamaPlannerModel()


class PlannerService:
    """Builds the prompt and delegates plan generation to a PlannerModel.

    Uses ``model`` as the primary planner and transparently falls back to
    ``fallback`` (the offline heuristic stub by default) if the primary raises or
    returns unparseable JSON. This keeps the app fully functional offline even
    when the LLM server is down.
    """

    def __init__(
        self,
        model: Optional[PlannerModel] = None,
        fallback: Optional[PlannerModel] = None,
        enable_fallback: bool = True,
        enable_deterministic_routing: bool = True,
    ) -> None:
        self._model = model or _default_model()
        self._fallback = fallback or HeuristicPlannerModel()
        self._enable_fallback = enable_fallback
        self._enable_deterministic_routing = enable_deterministic_routing
        self._last_model_name = self._model.name

    @property
    def model_name(self) -> str:
        """Name of the model that produced the most recent plan."""
        return self._last_model_name

    def set_model(self, model: PlannerModel) -> None:
        self._model = model

    def generate_plan(self, user_query: str, context: dict[str, Any]) -> str:
        """Return a raw JSON plan string for ``user_query``.

        Tries the primary model first; on any failure (unreachable LLM, invalid
        JSON) falls back to the heuristic stub so a valid plan is always returned.
        """
        if self._enable_deterministic_routing:
            routed = route_known_workflow(user_query, context)
            if routed is not None:
                self._last_model_name = "deterministic_router"
                return _complete_plan(json.dumps(routed), user_query, context)

        prompt = build_planner_prompt(user_query, context)
        try:
            raw = self._model.generate(prompt, user_query, context)
            json.loads(raw)  # ensure parseable before accepting
            self._last_model_name = self._model.name
            return _complete_plan(_repair_plan(raw, context), user_query, context)
        except Exception as exc:  # noqa: BLE001 - any failure -> safe fallback
            if not self._enable_fallback or self._fallback is self._model:
                raise
            _log.warning("planner '%s' failed (%s); falling back to '%s'",
                         self._model.name, exc, self._fallback.name)
            self._last_model_name = self._fallback.name
            fallback_raw = self._fallback.generate(prompt, user_query, context)
            return _complete_plan(_repair_plan(fallback_raw, context), user_query, context)


def _repair_plan(raw: str, context: dict[str, Any]) -> str:
    """Repair invented dependency references before deterministic completion."""
    data = json.loads(raw)
    steps = data.get("steps") or []
    seen_ids: list[str] = []
    intent_ids: dict[str, str] = {}

    for index, step in enumerate(steps, start=1):
        step_id = str(step.get("step_id") or f"step_{index}")
        if step_id in seen_ids:
            step_id = f"step_{index}"
        step["step_id"] = step_id
        intent = str(step.get("intent") or "")

        repaired_dependencies: list[str] = []
        for dependency in step.get("depends_on") or []:
            reference = str(dependency)
            resolved = reference if reference in seen_ids else intent_ids.get(reference)
            if resolved and resolved not in repaired_dependencies:
                repaired_dependencies.append(resolved)
        step["depends_on"] = repaired_dependencies

        inputs = step.setdefault("inputs", {})
        source = inputs.get("source_step")
        if source:
            resolved = str(source) if str(source) in seen_ids else intent_ids.get(str(source))
            if resolved:
                inputs["source_step"] = resolved
                if resolved not in step["depends_on"]:
                    step["depends_on"].append(resolved)
            else:
                inputs.pop("source_step", None)

        if intent in {"GENERATE_PDF", "GENERATE_PPTX"} and not step["depends_on"]:
            if context.get("latest_content_bundle"):
                inputs["reuse_latest_bundle"] = True

        seen_ids.append(step_id)
        intent_ids[intent] = step_id

    return json.dumps(data)


def _complete_plan(raw: str, user_query: str, context: dict[str, Any]) -> str:
    """Deterministically add missing evidence prerequisites and query context."""
    data = json.loads(raw)
    steps: list[dict[str, Any]] = data.get("steps", [])
    if not steps:
        return raw

    query_intents = {"SUMMARIZE_VIDEO", "SUMMARIZE_CHAT_HISTORY"}
    for step in steps:
        if step.get("intent") in query_intents:
            step.setdefault("inputs", {}).setdefault("query", user_query)

    if any(step.get("intent") == "CLARIFY" for step in steps):
        return json.dumps(data)

    available = context.get("available_analyses", {})
    present_intents = {step.get("intent") for step in steps}
    used_ids = {str(step.get("step_id")) for step in steps}
    auto_index = 1

    def next_id(label: str) -> str:
        nonlocal auto_index
        while f"auto_{label}_{auto_index}" in used_ids:
            auto_index += 1
        value = f"auto_{label}_{auto_index}"
        used_ids.add(value)
        auto_index += 1
        return value

    summary_ids = {
        str(step.get("step_id"))
        for step in steps
        if step.get("intent") == "SUMMARIZE_VIDEO"
    }
    report_steps = [
        step for step in steps if step.get("intent") in {"GENERATE_PDF", "GENERATE_PPTX"}
    ]
    reusable_report = any(
        step.get("inputs", {}).get("reuse_latest_bundle") for step in report_steps
    )
    if (
        report_steps
        and not summary_ids
        and not reusable_report
        and all(not step.get("depends_on") for step in report_steps)
        and context.get("current_video")
        and not context.get("available_analyses", {}).get("summary")
    ):
        summary_id = next_id("summary")
        steps.insert(
            0,
            _step(summary_id, "SUMMARIZE_VIDEO", "summary_agent", {"query": user_query}, []),
        )
        summary_ids.add(summary_id)
        for step in report_steps:
            step["depends_on"] = [summary_id]
            step.setdefault("inputs", {})["source_step"] = summary_id

    prereqs: list[dict[str, Any]] = []
    prereq_ids: list[str] = []
    if context.get("current_video") and summary_ids and not available.get("transcript") and "TRANSCRIBE_VIDEO" not in present_intents:
        step_id = next_id("transcript")
        prereqs.append(
            {
                **_step(step_id, "TRANSCRIBE_VIDEO", "transcription_agent", {"auto_prerequisite": True}, []),
                "optional": True,
            }
        )
        prereq_ids.append(step_id)
    has_visual = any(available.get(key) for key in ("objects", "ocr", "graphs"))
    visual_intents = {"ANALYZE_OBJECTS", "COUNT_OBJECTS", "DETECT_GRAPHS", "ANALYZE_OCR"}
    if context.get("current_video") and summary_ids and not has_visual and not present_intents.intersection(visual_intents):
        step_id = next_id("vision")
        prereqs.append(
            {
                **_step(step_id, "ANALYZE_OBJECTS", "vision_agent", {"auto_prerequisite": True}, []),
                "optional": True,
            }
        )
        prereq_ids.append(step_id)

    for step in steps:
        if step.get("intent") == "SUMMARIZE_VIDEO":
            existing = list(step.get("depends_on") or [])
            step["depends_on"] = [*prereq_ids, *[item for item in existing if item not in prereq_ids]]
    data["steps"] = [*prereqs, *steps]
    return json.dumps(data)
