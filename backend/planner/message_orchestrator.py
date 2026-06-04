"""Message orchestrator (Phase 7).

Ties the planner pipeline together for a single user message:

    save user msg -> build context -> generate plan -> validate
      -> if clarification needed: persist pending question, reply with it
      -> else: execute plan, persist generated files, reply with result
    -> save assistant message

Used by the gRPC ``SendMessage`` handler and exercised directly by the Phase 7
smoke test. Returns a plain dict so the transport layer just maps fields.
"""

from __future__ import annotations

from typing import Any

from backend.context.context_builder import ContextBuilder
from backend.mcp_clients.mcp_client_manager import MCPClientManager
from backend.planner.clarification_manager import ClarificationManager
from backend.planner.plan_executor import PlanExecutor
from backend.planner.plan_validator import PlanValidator
from backend.planner.planner_service import PlannerService
from backend.session.session_manager import SessionManager
from backend.storage.db import Database

_ANALYSIS_TYPES = ("transcript", "objects", "ocr", "graphs", "summary")


class MessageOrchestrator:
    def __init__(
        self,
        db: Database,
        sessions: SessionManager | None = None,
        mcp: MCPClientManager | None = None,
        planner: PlannerService | None = None,
    ) -> None:
        self._db = db
        self._sessions = sessions or SessionManager(db)
        self._context = ContextBuilder(self._sessions, db)
        self._mcp = mcp or MCPClientManager()
        self._planner = planner or PlannerService()
        self._validator = PlanValidator()
        self._executor = PlanExecutor(self._mcp, db)
        self._clarify = ClarificationManager(db)

    async def handle_message(self, session_id: str, message: str) -> dict[str, Any]:
        self._sessions.save_chat_message(session_id, "user", message)

        context = self._context.build(session_id)
        context["has_analyses"] = self._has_analyses(context)

        raw_plan = self._planner.generate_plan(message, context)
        result = self._validator.validate(raw_plan, context)

        if not result.valid:
            reply = (
                "I couldn't build a valid plan for that request. "
                "Could you rephrase it?"
            )
            self._sessions.save_chat_message(session_id, "assistant", reply)
            return self._response(reply, planner=self._planner.model_name, error=result.error)

        if result.needs_clarification:
            question = result.clarification_question or "Could you clarify your request?"
            self._clarify.set_pending(session_id, question)
            self._sessions.save_chat_message(session_id, "assistant", question)
            return self._response(question, clarification=True, planner=self._planner.model_name)

        # Valid, executable plan: clear any stale clarification and run it.
        self._clarify.clear(session_id)
        execution = await self._executor.execute(result.plan, context)

        for f in execution.generated_files:
            self._db.save_generated_file(
                session_id, f.get("file_type", "file"), f["file_path"],
                video_id=(context.get("current_video") or {}).get("video_id"),
            )

        self._sessions.save_chat_message(session_id, "assistant", execution.assistant_message)
        return self._response(
            execution.assistant_message,
            generated_files=execution.generated_files,
            planner=self._planner.model_name,
        )

    def _has_analyses(self, context: dict[str, Any]) -> bool:
        video = context.get("current_video")
        if not video:
            return False
        vid = video["video_id"]
        return any(self._db.get_latest_analysis(vid, t) for t in _ANALYSIS_TYPES)

    @staticmethod
    def _response(
        assistant_message: str,
        *,
        clarification: bool = False,
        clarification_question: str | None = None,
        generated_files: list[dict[str, Any]] | None = None,
        planner: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return {
            "assistant_message": assistant_message,
            "clarification_needed": clarification,
            "clarification_question": clarification_question
            or (assistant_message if clarification else ""),
            "generated_files": generated_files or [],
            "planner": planner,
            "error": error,
        }
