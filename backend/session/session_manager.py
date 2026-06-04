"""SessionManager for the Intel Local Video AI MVP (Phase 1).

Owns session lifecycle, the current video association, chat persistence, and the
pending-clarification flag. It is a thin orchestration layer over ``Database``;
it deliberately holds no hidden global state (the DB is the source of truth).
"""

from __future__ import annotations

from typing import Any, Optional

from backend.storage.db import Database


class SessionManager:
    """Create/load sessions and manage their video + chat state."""

    def __init__(self, db: Database) -> None:
        self._db = db

    @property
    def db(self) -> Database:
        """Underlying storage (used by the planner pipeline / gRPC layer)."""
        return self._db

    # ------------------------------------------------------------------ #
    # sessions
    # ------------------------------------------------------------------ #
    def create_session(self, title: Optional[str] = None) -> dict[str, Any]:
        return self._db.create_session(title)

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._db.get_session(session_id)

    def require_session(self, session_id: str) -> dict[str, Any]:
        session = self._db.get_session(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id!r}")
        return session

    # ------------------------------------------------------------------ #
    # videos
    # ------------------------------------------------------------------ #
    def save_video(self, session_id: str, video_path: str, **metadata: Any) -> dict[str, Any]:
        """Store a video for the session and make it the current video."""
        self.require_session(session_id)
        video = self._db.save_video(session_id, video_path, **metadata)
        self._db.set_current_video(session_id, video["video_id"])
        return video

    def set_current_video(self, session_id: str, video_id: str) -> None:
        self.require_session(session_id)
        self._db.set_current_video(session_id, video_id)

    def get_current_video(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._db.get_current_video(session_id)

    # ------------------------------------------------------------------ #
    # chat
    # ------------------------------------------------------------------ #
    def save_chat_message(self, session_id: str, role: str, content: str) -> dict[str, Any]:
        self.require_session(session_id)
        return self._db.save_chat_message(session_id, role, content)

    def get_recent_messages(self, session_id: str, limit: int = 20) -> list[dict[str, Any]]:
        return self._db.get_recent_messages(session_id, limit)

    # ------------------------------------------------------------------ #
    # clarification
    # ------------------------------------------------------------------ #
    def set_pending_clarification(self, session_id: str, question: Optional[str]) -> None:
        self.require_session(session_id)
        self._db.set_pending_clarification(session_id, question)

    def get_pending_clarification(self, session_id: str) -> Optional[str]:
        session = self.get_session(session_id)
        return session.get("pending_clarification") if session else None

    def clear_pending_clarification(self, session_id: str) -> None:
        self.set_pending_clarification(session_id, None)
