"""Plan executor (Phase 7).

Executes a validated :class:`Plan`:
- Runs steps in listed order (dependencies always precede dependents).
- Resolves ``inputs.source_step`` / ``depends_on`` by injecting the referenced
  step's result data into the dependent step's inputs as ``source_result``.
- Dispatches each step to the right agent via a name->agent registry.
- Aggregates generated files and a human-readable final response.

Agents are deterministic orchestrators; the executor owns ordering + wiring only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.agents.base_agent import AgentResult
from backend.agents.clarification_agent import ClarificationAgent
from backend.agents.report_agent import ReportAgent
from backend.agents.summary_agent import SummaryAgent
from backend.agents.transcription_agent import TranscriptionAgent
from backend.agents.vision_agent import VisionAgent
from backend.mcp_clients.mcp_client_manager import MCPClientManager
from backend.planner.plan_schema import Agent, Intent, Plan, PlanStep
from backend.storage.db import Database

# Report intent -> export format injected into report_agent inputs.
_REPORT_FORMAT = {Intent.GENERATE_PDF: "pdf", Intent.GENERATE_PPTX: "pptx"}


@dataclass
class ExecutionResult:
    assistant_message: str
    generated_files: list[dict[str, Any]] = field(default_factory=list)
    step_results: dict[str, AgentResult] = field(default_factory=dict)
    success: bool = True


class PlanExecutor:
    def __init__(self, mcp: MCPClientManager, db: Database) -> None:
        self._registry = {
            Agent.TRANSCRIPTION.value: TranscriptionAgent(mcp, db),
            Agent.VISION.value: VisionAgent(mcp, db),
            Agent.SUMMARY.value: SummaryAgent(mcp, db),
            Agent.REPORT.value: ReportAgent(mcp, db),
            Agent.CLARIFICATION.value: ClarificationAgent(mcp, db),
        }

    async def execute(self, plan: Plan, context: dict[str, Any]) -> ExecutionResult:
        results: dict[str, AgentResult] = {}
        files: list[dict[str, Any]] = []
        summaries: list[str] = []
        overall_ok = True

        for step in plan.steps:
            inputs = self._prepare_inputs(step, results)
            agent = self._registry.get(step.agent.value)
            if agent is None:
                results[step.step_id] = AgentResult(
                    step.agent.value, step.intent.value, False,
                    f"no agent registered for {step.agent.value}",
                    error="unregistered agent",
                )
                overall_ok = False
                break

            result = await agent.handle(step.intent.value, inputs, context)
            results[step.step_id] = result
            summaries.append(result.summary)

            if not result.success:
                overall_ok = False
                break

            for f in result.data.get("files", []):
                files.append(f)

        message = self._compose_message(summaries, overall_ok)
        return ExecutionResult(message, files, results, overall_ok)

    def _prepare_inputs(self, step: PlanStep, results: dict[str, AgentResult]) -> dict[str, Any]:
        inputs = dict(step.inputs)

        # Inject report export format from the intent.
        if step.intent in _REPORT_FORMAT:
            inputs.setdefault("format", _REPORT_FORMAT[step.intent])

        # Resolve source_step / first dependency into source_result.
        source_id = inputs.get("source_step")
        if not source_id and step.depends_on:
            source_id = step.depends_on[0]
        if source_id and source_id in results:
            inputs["source_result"] = results[source_id].data

        return inputs

    @staticmethod
    def _compose_message(summaries: list[str], ok: bool) -> str:
        body = " ".join(s for s in summaries if s)
        if not body:
            body = "Done." if ok else "I couldn't complete the request."
        return body
