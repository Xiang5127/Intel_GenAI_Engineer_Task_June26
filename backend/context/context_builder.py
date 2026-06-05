"""ContextBuilder for the Intel Local Video AI MVP (Phase 1).

Builds a compact, planner-friendly context object from session state. It does
NOT dump everything blindly: it includes only the current video status, a bounded
window of recent messages, the pending clarification, and recent generated files.

In Phase 1 this is consumed by the CLI smoke test; from Phase 7 it feeds the
PlannerService.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.session.session_manager import SessionManager
from backend.storage.db import Database


class ContextBuilder:
    """Assemble compact context for the planner / dummy responder."""

    def __init__(
        self,
        session_manager: SessionManager,
        db: Database,
        recent_message_limit: int = 10,
        recent_file_limit: int = 5,
    ) -> None:
        self._sessions = session_manager
        self._db = db
        self._recent_message_limit = recent_message_limit
        self._recent_file_limit = recent_file_limit

    def build(self, session_id: str) -> dict[str, Any]:
        session = self._sessions.require_session(session_id)
        current_video = self._sessions.get_current_video(session_id)
        recent_messages = self._sessions.get_recent_messages(
            session_id, self._recent_message_limit
        )
        generated_files = self._db.get_generated_files(
            session_id, self._recent_file_limit
        )
        latest_bundle = self._db.get_latest_content_bundle(session_id)

        return {
            "session_id": session_id,
            "current_video": self._video_summary(current_video),
            "recent_messages": [
                {"role": m["role"], "content": m["content"], "created_at": m["created_at"]}
                for m in recent_messages
            ],
            "pending_clarification": session.get("pending_clarification"),
            "generated_files": [
                {"file_type": f["file_type"], "file_path": f["file_path"]}
                for f in generated_files
            ],
            "latest_content_bundle": (
                {
                    "bundle_id": latest_bundle["bundle_id"],
                    "source_kind": latest_bundle["source_kind"],
                    "video_id": latest_bundle.get("video_id"),
                    "query": latest_bundle.get("query"),
                }
                if latest_bundle
                else None
            ),
        }

    @staticmethod
    def _video_summary(video: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        if not video:
            return None
        return {
            "video_id": video["video_id"],
            "video_path": video["video_path"],
            "duration_seconds": video.get("duration_seconds"),
            "width": video.get("width"),
            "height": video.get("height"),
            "fps": video.get("fps"),
        }
