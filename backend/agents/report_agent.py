"""ReportAgent (Phase 6).

Generates PDF/PPTX deliverables from a *normalized* ``report_data`` /
``slide_data`` bundle and records the output files in storage.

Source of the bundle (in priority order):
1. Explicit ``report_data`` / ``slide_data`` in ``inputs`` (e.g. passed from a
   previous SummaryAgent step by the PlanExecutor).
2. A normalized bundle from ``source_result``.
3. The latest stored ``summary`` analysis for the current video when no
   query-specific content was requested.
4. Built on demand via :class:`SummaryAgent`.

The agent is agnostic to whether the summary was produced by rules or an LLM; it
only depends on the normalized structure.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from backend.agents.base_agent import AgentResult, BaseAgent
from backend.agents.summary_agent import SummaryAgent

_VALID_FORMATS = ("pdf", "pptx", "both")


class ReportAgent(BaseAgent):
    name = "report_agent"

    async def handle(
        self,
        intent: str,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentResult:
        session_id = context.get("session_id")
        video = self._current_video(context)
        video_id = (video or {}).get("video_id")

        fmt = str(inputs.get("format", "pdf")).lower()
        if fmt not in _VALID_FORMATS:
            return self._fail(intent, f"invalid format '{fmt}' (use pdf, pptx, or both)")

        bundle = await self._resolve_bundle(inputs, context, video_id)
        if bundle is None:
            return self._fail(
                intent,
                "no report content available; run analyses/summary first",
            )
        report_data = bundle.get("report_data")
        slide_data = bundle.get("slide_data")

        generated: list[dict[str, Any]] = []
        try:
            if fmt in ("pdf", "both"):
                res = await self.mcp.call_tool(
                    "report", "generate_pdf_report", {"report_data": report_data}
                )
                generated.append(res)
            if fmt in ("pptx", "both"):
                res = await self.mcp.call_tool(
                    "report", "generate_pptx_report", {"slide_data": slide_data}
                )
                generated.append(res)
        except Exception as exc:  # noqa: BLE001
            return self._fail(intent, f"report generation failed: {exc}")

        # Record generated files.
        if session_id:
            for g in generated:
                self.db.save_generated_file(
                    session_id, g["file_type"], g["file_path"], video_id=video_id
                )

        paths = ", ".join(g["file_path"] for g in generated)
        summary = f"Generated {len(generated)} file(s): {paths}"
        return self._ok(intent, summary, {"files": generated})

    async def _resolve_bundle(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
        video_id: Optional[str],
    ) -> Optional[dict[str, Any]]:
        # 1. Explicit bundle from inputs (e.g. previous step output).
        if inputs.get("report_data") and inputs.get("slide_data"):
            return {
                "report_data": inputs["report_data"],
                "slide_data": inputs["slide_data"],
            }
        source_result = inputs.get("source_result") or {}
        if source_result.get("report_data") and source_result.get("slide_data"):
            return {
                "report_data": source_result["report_data"],
                "slide_data": source_result["slide_data"],
            }

        if not video_id:
            return None

        # 2. Latest stored summary.
        if not inputs.get("force_summary") and not inputs.get("query") and not source_result:
            row = self.db.get_latest_analysis(video_id, "summary")
            if row:
                return json.loads(row["result_json"])

        # 3. Build on demand via SummaryAgent.
        summary_agent = SummaryAgent(self.mcp, self.db)
        result = await summary_agent.handle(
            "SUMMARIZE_VIDEO",
            {"query": inputs.get("query"), "source_result": source_result},
            context,
        )
        if not result.success:
            return None
        return {"report_data": result.data["report_data"], "slide_data": result.data["slide_data"]}
