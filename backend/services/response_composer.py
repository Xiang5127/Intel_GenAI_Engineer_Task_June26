"""Concise deterministic user-facing responses for completed plans."""

from __future__ import annotations

import re
from typing import Any

from backend.planner.plan_schema import Intent, Plan
from backend.planner.plan_executor import ExecutionResult

MAX_RESPONSE_WORDS = 120


def compose_response(plan: Plan, execution: ExecutionResult) -> str:
    """Return a short response without exposing internal model or agent details."""
    if not execution.success:
        return _limit_words(_sanitize(execution.assistant_message))

    intents = {step.intent for step in plan.steps}
    formats = [str(item.get("file_type", "file")).upper() for item in execution.generated_files]
    if formats:
        created = " and ".join(dict.fromkeys(formats))
        if Intent.SUMMARIZE_CHAT_HISTORY in intents:
            return f"Created {created} with a summary of the discussion."
        if any(step.inputs.get("reuse_latest_bundle") for step in plan.steps):
            return f"Created {created} from the latest report content."
        return f"Created {created}."

    if (
        Intent.TRANSCRIBE_VIDEO in intents
        and Intent.SUMMARIZE_VIDEO not in intents
        and Intent.SUMMARIZE_CHAT_HISTORY not in intents
    ):
        transcript = _transcript_text(execution)
        if transcript:
            return f"Transcript:\n\n{transcript}"

    summary_result = next(
        (
            result
            for result in reversed(list(execution.step_results.values()))
            if result.intent in {Intent.SUMMARIZE_VIDEO.value, Intent.SUMMARIZE_CHAT_HISTORY.value}
            and result.success
        ),
        None,
    )
    if summary_result:
        answer = _answer_from_bundle(summary_result.data)
        return _limit_words(_sanitize(answer or "Summary completed."))

    successful = [
        _sanitize(result.summary)
        for result in execution.step_results.values()
        if result.success and result.summary
    ]
    return _limit_words(" ".join(successful) or "Done.")


def _answer_from_bundle(bundle: dict[str, Any]) -> str:
    sections = (bundle.get("report_data") or {}).get("sections") or []
    parts: list[str] = []
    for section in sections[:2]:
        body = str(section.get("body") or "").strip()
        bullets = [str(item).strip() for item in (section.get("bullets") or [])[:4]]
        if body:
            parts.append(body)
        if bullets:
            parts.append(" ".join(f"- {item}" for item in bullets))
    return " ".join(parts)


def _transcript_text(execution: ExecutionResult) -> str:
    result = next(
        (
            item
            for item in reversed(list(execution.step_results.values()))
            if item.intent == Intent.TRANSCRIBE_VIDEO.value and item.success
        ),
        None,
    )
    if not result:
        return ""
    transcript = result.data.get("transcript") or {}
    return str(transcript.get("text") or "").strip()


def _sanitize(text: str) -> str:
    text = str(text or "")
    replacements = {
        r"ollama:[^\s,.;]+": "local analysis",
        r"qwen[^\s,.;]*": "local analysis",
        r"\b\w+_agent\b": "analysis",
        r"\bsummarizer\b": "analysis",
        r"\bplanner\b": "routing",
        r"detection backend unavailable \([^)]*\)": "object detection is unavailable",
        r"\bbackend:\s*[^,.)]+": "local detection",
        r",?\s*available:\s*(?:true|false|none)": "",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return " ".join(text.split())


def _limit_words(text: str) -> str:
    words = text.split()
    if len(words) <= MAX_RESPONSE_WORDS:
        return text
    return " ".join(words[:MAX_RESPONSE_WORDS]).rstrip(" ,.;:") + "..."
