"""Clarification manager (Phase 7).

Persists/clears the session's pending clarification so the next user message can
be interpreted as an answer to the outstanding question. Thin wrapper over the
storage layer; kept separate so the planner flow has a single clarification API.
"""

from __future__ import annotations

from typing import Optional

from backend.storage.db import Database


class ClarificationManager:
    def __init__(self, db: Database) -> None:
        self._db = db

    def set_pending(self, session_id: str, question: str) -> None:
        self._db.set_pending_clarification(session_id, question)

    def get_pending(self, session_id: str) -> Optional[str]:
        session = self._db.get_session(session_id)
        return session.get("pending_clarification") if session else None

    def clear(self, session_id: str) -> None:
        self._db.set_pending_clarification(session_id, None)
