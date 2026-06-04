"""ClarificationAgent (Phase 7).

A trivial agent for CLARIFY steps: it surfaces the clarification question as the
step result. The PlanExecutor / gRPC layer is responsible for persisting the
pending clarification on the session.
"""

from __future__ import annotations

from typing import Any

from backend.agents.base_agent import AgentResult, BaseAgent


class ClarificationAgent(BaseAgent):
    name = "clarification_agent"

    async def handle(
        self,
        intent: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        question = inputs.get("question") or "Could you clarify your request?"
        return self._ok(intent, question, {"clarification_question": question})
