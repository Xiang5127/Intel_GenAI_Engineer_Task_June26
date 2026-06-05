"""Deterministic routing for common, well-defined user workflows."""

from __future__ import annotations

from typing import Any, Optional


def _step(
    step_id: str,
    intent: str,
    agent: str,
    inputs: Optional[dict[str, Any]] = None,
    depends_on: Optional[list[str]] = None,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "intent": intent,
        "agent": agent,
        "inputs": inputs or {},
        "depends_on": depends_on or [],
    }


def _plan(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {"confidence": 0.99, "steps": steps, "clarification_question": None}


def _clarify(question: str) -> dict[str, Any]:
    return {
        "confidence": 0.45,
        "steps": [_step("step_1", "CLARIFY", "clarification_agent", {"question": question})],
        "clarification_question": question,
    }


def route_known_workflow(
    user_query: str, context: dict[str, Any]
) -> Optional[dict[str, Any]]:
    """Return a deterministic plan for supported commands, otherwise ``None``."""
    query = (user_query or "").strip()
    q = query.casefold()
    if not q:
        return _clarify("What would you like me to do?")

    has_video = bool(context.get("current_video"))
    has_bundle = bool(context.get("latest_content_bundle"))
    available = context.get("available_analyses") or {}
    has_summary = bool(available.get("summary"))

    wants_pdf = "pdf" in q
    wants_pptx = any(word in q for word in ("pptx", "powerpoint", "power point", "slides", "presentation"))
    wants_export = wants_pdf or wants_pptx
    mentions_report = any(word in q for word in ("report", "export", "generate", "create", "make"))
    asks_summary = any(word in q for word in ("summar", "recap", "sum up", "key points", "main points"))
    chat_source = any(
        word in q
        for word in ("our discussion", "discussion so far", "our conversation", "conversation so far", "chat history")
    )

    if mentions_report and not wants_export and "report" in q:
        return _clarify("Do you want a PDF report or a PowerPoint presentation?")

    primary: Optional[dict[str, Any]] = None
    if "transcri" in q:
        primary = _step("step_1", "TRANSCRIBE_VIDEO", "transcription_agent")
    elif "how many" in q or "count " in q:
        primary = _step(
            "step_1",
            "COUNT_OBJECTS",
            "vision_agent",
            {"target": _count_target(q)},
        )
    elif any(word in q for word in ("graph", "chart", "plot")) and not wants_export:
        primary = _step("step_1", "DETECT_GRAPHS", "vision_agent")
    elif any(word in q for word in ("ocr", "text on screen", "on-screen text", "read text", "written")):
        primary = _step("step_1", "ANALYZE_OCR", "vision_agent")
    elif any(word in q for word in ("object", "what is shown", "what's shown", "what do you see", "detect")):
        primary = _step("step_1", "ANALYZE_OBJECTS", "vision_agent")
    elif chat_source and (asks_summary or wants_export):
        primary = _step(
            "step_1",
            "SUMMARIZE_CHAT_HISTORY",
            "summary_agent",
            {"query": query},
        )
    elif asks_summary:
        primary = _step("step_1", "SUMMARIZE_VIDEO", "summary_agent", {"query": query})
    elif _looks_like_video_question(q, has_video):
        primary = _step("step_1", "SUMMARIZE_VIDEO", "summary_agent", {"query": query})

    if wants_export:
        if primary is not None:
            steps = [primary, *_report_steps(q, source_step=primary["step_id"])]
            return _plan(steps)
        if has_bundle:
            return _plan(_report_steps(q, reuse_latest_bundle=True))
        if has_summary:
            return _plan(_report_steps(q))
        if has_video:
            summary = _step("step_1", "SUMMARIZE_VIDEO", "summary_agent", {"query": query})
            return _plan([summary, *_report_steps(q, source_step=summary["step_id"])])
        return _clarify("There is no summary content to export yet.")

    if primary is not None:
        return _plan([primary])
    return None


def _report_steps(
    query: str,
    *,
    source_step: Optional[str] = None,
    reuse_latest_bundle: bool = False,
) -> list[dict[str, Any]]:
    inputs: dict[str, Any] = {}
    dependencies: list[str] = []
    if source_step:
        inputs["source_step"] = source_step
        dependencies = [source_step]
    if reuse_latest_bundle:
        inputs["reuse_latest_bundle"] = True

    steps: list[dict[str, Any]] = []
    if "pdf" in query:
        steps.append(_step("step_pdf", "GENERATE_PDF", "report_agent", dict(inputs), dependencies))
    if any(word in query for word in ("pptx", "powerpoint", "power point", "slides", "presentation")):
        steps.append(_step("step_pptx", "GENERATE_PPTX", "report_agent", dict(inputs), dependencies))
    return steps


def _count_target(query: str) -> str:
    marker = "how many " if "how many " in query else "count "
    tail = query.split(marker, 1)[1] if marker in query else "objects"
    for stop in (" are ", " is ", " in ", " on ", " appear", " and ", "?", "."):
        tail = tail.split(stop, 1)[0]
    return tail.strip() or "objects"


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
        )
    )
