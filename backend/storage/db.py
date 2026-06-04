"""SQLite storage layer for the Intel Local Video AI MVP (Phase 1).

Provides database initialization from ``schema.sql`` and typed CRUD helpers for
sessions, chat messages, videos, video analysis, and generated files.

All timestamps are unix epoch seconds (int). No business logic lives here; the
SessionManager and agents build on top of these primitives.
"""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# backend/ root (this file is backend/storage/db.py).
BACKEND_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = BACKEND_DIR / "storage" / "schema.sql"
DEFAULT_DB_PATH = BACKEND_DIR / "storage" / "video_ai.db"


def _now() -> int:
    """Current unix epoch seconds."""
    return int(time.time())


def _new_id(prefix: str) -> str:
    """Generate a short prefixed unique id, e.g. ``session_ab12cd34``."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Database:
    """Thin wrapper around a SQLite connection with CRUD helpers."""

    def __init__(self, db_path: Optional[os.PathLike[str] | str] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")

    # ------------------------------------------------------------------ #
    # lifecycle
    # ------------------------------------------------------------------ #
    def initialize(self, schema_path: Optional[os.PathLike[str] | str] = None) -> None:
        """Create tables/indexes from ``schema.sql`` (idempotent)."""
        path = Path(schema_path) if schema_path is not None else SCHEMA_PATH
        sql = path.read_text(encoding="utf-8")
        self._conn.executescript(sql)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # sessions
    # ------------------------------------------------------------------ #
    def create_session(self, title: Optional[str] = None) -> dict[str, Any]:
        session_id = _new_id("session")
        ts = _now()
        self._conn.execute(
            """
            INSERT INTO sessions (session_id, title, current_video_id,
                                  pending_clarification, created_at, updated_at)
            VALUES (?, ?, NULL, NULL, ?, ?)
            """,
            (session_id, title, ts, ts),
        )
        self._conn.commit()
        return self.get_session(session_id)  # type: ignore[return-value]

    def get_session(self, session_id: str) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def set_pending_clarification(
        self, session_id: str, question: Optional[str]
    ) -> None:
        self._conn.execute(
            "UPDATE sessions SET pending_clarification = ?, updated_at = ? "
            "WHERE session_id = ?",
            (question, _now(), session_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------ #
    # chat messages
    # ------------------------------------------------------------------ #
    def save_chat_message(
        self, session_id: str, role: str, content: str
    ) -> dict[str, Any]:
        if role not in ("user", "assistant", "system"):
            raise ValueError(f"invalid role: {role!r}")
        message_id = _new_id("msg")
        ts = _now()
        self._conn.execute(
            """
            INSERT INTO chat_messages (message_id, session_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (message_id, session_id, role, content, ts),
        )
        self._conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?", (ts, session_id)
        )
        self._conn.commit()
        return {
            "message_id": message_id,
            "session_id": session_id,
            "role": role,
            "content": content,
            "created_at": ts,
        }

    def get_recent_messages(
        self, session_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        """Return up to ``limit`` most recent messages in chronological order.

        ``limit <= 0`` returns the full history.
        """
        if limit and limit > 0:
            rows = self._conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------ #
    # videos
    # ------------------------------------------------------------------ #
    def save_video(
        self,
        session_id: str,
        video_path: str,
        duration_seconds: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        fps: Optional[float] = None,
    ) -> dict[str, Any]:
        video_id = _new_id("video")
        ts = _now()
        self._conn.execute(
            """
            INSERT INTO videos (video_id, session_id, video_path, duration_seconds,
                                width, height, fps, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (video_id, session_id, video_path, duration_seconds, width, height, fps, ts),
        )
        self._conn.commit()
        return self.get_video(video_id)  # type: ignore[return-value]

    def get_video(self, video_id: str) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM videos WHERE video_id = ?", (video_id,)
        ).fetchone()
        return dict(row) if row else None

    def set_current_video(self, session_id: str, video_id: str) -> None:
        self._conn.execute(
            "UPDATE sessions SET current_video_id = ?, updated_at = ? "
            "WHERE session_id = ?",
            (video_id, _now(), session_id),
        )
        self._conn.commit()

    def get_current_video(self, session_id: str) -> Optional[dict[str, Any]]:
        session = self.get_session(session_id)
        if not session or not session.get("current_video_id"):
            return None
        return self.get_video(session["current_video_id"])

    # ------------------------------------------------------------------ #
    # video analysis
    # ------------------------------------------------------------------ #
    def save_video_analysis(
        self, video_id: str, analysis_type: str, result_json: str
    ) -> dict[str, Any]:
        analysis_id = _new_id("analysis")
        ts = _now()
        self._conn.execute(
            """
            INSERT INTO video_analysis (analysis_id, video_id, analysis_type,
                                        result_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (analysis_id, video_id, analysis_type, result_json, ts),
        )
        self._conn.commit()
        return {
            "analysis_id": analysis_id,
            "video_id": video_id,
            "analysis_type": analysis_type,
            "result_json": result_json,
            "created_at": ts,
        }

    def get_latest_analysis(
        self, video_id: str, analysis_type: str
    ) -> Optional[dict[str, Any]]:
        row = self._conn.execute(
            """
            SELECT * FROM video_analysis
            WHERE video_id = ? AND analysis_type = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT 1
            """,
            (video_id, analysis_type),
        ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------ #
    # generated files
    # ------------------------------------------------------------------ #
    def save_generated_file(
        self,
        session_id: str,
        file_type: str,
        file_path: str,
        video_id: Optional[str] = None,
    ) -> dict[str, Any]:
        file_id = _new_id("file")
        ts = _now()
        self._conn.execute(
            """
            INSERT INTO generated_files (file_id, session_id, video_id, file_type,
                                         file_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (file_id, session_id, video_id, file_type, file_path, ts),
        )
        self._conn.commit()
        return {
            "file_id": file_id,
            "session_id": session_id,
            "video_id": video_id,
            "file_type": file_type,
            "file_path": file_path,
            "created_at": ts,
        }

    def get_generated_files(
        self, session_id: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT * FROM generated_files
            WHERE session_id = ?
            ORDER BY created_at DESC, rowid DESC
            LIMIT ?
            """,
            (session_id, limit if limit and limit > 0 else -1),
        ).fetchall()
        return [dict(r) for r in rows]


def init_db(db_path: Optional[os.PathLike[str] | str] = None) -> Database:
    """Convenience: open a database and ensure the schema exists."""
    db = Database(db_path)
    db.initialize()
    return db
