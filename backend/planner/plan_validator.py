"""Plan validator (Phase 7).

Parses the raw JSON plan and enforces the rules from ``03_PLAN_SCHEMA.md``:
- Valid JSON + schema (via Pydantic).
- confidence >= MIN_CONFIDENCE unless the plan is a CLARIFY.
- Every agent/intent allowed (enforced by enums) and agent matches its intent.
- depends_on references existing prior steps; no cycles.
- Video-required intents need a selected video.
- CLARIFY must include a clarification question.
- Report steps need a source step, existing analyses, or a reusable content bundle.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import ValidationError

from backend.planner.plan_schema import (
    INTENT_TO_AGENT,
    MIN_CONFIDENCE,
    REPORT_INTENTS,
    VIDEO_REQUIRED_INTENTS,
    Intent,
    Plan,
)


@dataclass
class ValidationResult:
    valid: bool
    plan: Optional[Plan] = None
    error: Optional[str] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


class PlanValidator:
    def validate(self, raw_plan: str, context: dict[str, Any]) -> ValidationResult:
        # 1. Parse JSON + schema.
        try:
            data = json.loads(raw_plan)
        except (json.JSONDecodeError, TypeError) as exc:
            return ValidationResult(False, error=f"plan is not valid JSON: {exc}")
        try:
            plan = Plan.model_validate(data)
        except ValidationError as exc:
            return ValidationResult(False, error=f"plan failed schema validation: {exc}")

        if not plan.steps:
            return ValidationResult(False, error="plan has no steps")

        # 2. Clarification handling.
        if plan.is_clarification():
            clarify = next(s for s in plan.steps if s.intent == Intent.CLARIFY)
            question = plan.clarification_question or clarify.inputs.get("question")
            if not question:
                return ValidationResult(False, error="CLARIFY plan missing a clarification question")
            return ValidationResult(
                True, plan=plan, needs_clarification=True, clarification_question=question
            )

        # 3. Confidence gate (non-clarify).
        if plan.confidence < MIN_CONFIDENCE:
            return ValidationResult(
                True,
                plan=plan,
                needs_clarification=True,
                clarification_question="I'm not fully sure what you'd like. "
                "Could you rephrase or add detail?",
            )

        # 4. Per-step structural + semantic checks.
        seen: set[str] = set()
        has_video = bool(context.get("current_video"))
        has_analyses = bool(context.get("has_analyses"))
        has_content_bundle = bool(context.get("latest_content_bundle"))

        for step in plan.steps:
            # agent matches intent
            expected = INTENT_TO_AGENT.get(step.intent)
            if expected is None:
                return ValidationResult(False, error=f"unknown intent: {step.intent}")
            if step.agent != expected:
                return ValidationResult(
                    False,
                    error=f"intent {step.intent.value} must use {expected.value}, "
                    f"got {step.agent.value}",
                )
            if step.optional and not step.inputs.get("auto_prerequisite"):
                return ValidationResult(
                    False,
                    error=f"step {step.step_id} may be optional only when auto-added",
                )

            # dependencies reference prior steps (acyclic by construction)
            for dep in step.depends_on:
                if dep not in seen:
                    return ValidationResult(
                        False,
                        error=f"step {step.step_id} depends on unknown/forward step '{dep}'",
                    )
            if step.step_id in seen:
                return ValidationResult(False, error=f"duplicate step_id: {step.step_id}")

            # video-required intents
            if step.intent in VIDEO_REQUIRED_INTENTS and not has_video:
                return ValidationResult(
                    True,
                    plan=plan,
                    needs_clarification=True,
                    clarification_question="Please select a video first, then resend your request.",
                )

            # report steps need source or stored analyses
            if (
                step.intent in REPORT_INTENTS
                and not step.depends_on
                and not has_analyses
                and not has_content_bundle
            ):
                return ValidationResult(
                    True,
                    plan=plan,
                    needs_clarification=True,
                    clarification_question="There's no analysis to report on yet. "
                    "Tell me what to analyze (e.g. transcribe or detect objects) first.",
                )

            seen.add(step.step_id)

        return ValidationResult(True, plan=plan)
