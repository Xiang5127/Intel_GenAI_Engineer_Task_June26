"""gRPC server skeleton for the Intel Local Video AI MVP (Phase 2).

Implements the four ``VideoAIService`` methods over the Phase 1 storage layer:
``CreateSession``, ``UploadVideo``, ``SendMessage`` (dummy response), and
``GetChatHistory``. No planner / agents / MCP yet.

The generated stubs (``video_ai_pb2`` / ``video_ai_pb2_grpc``) use flat imports,
so the generated directory is placed on ``sys.path`` before importing them.
"""

from __future__ import annotations

import asyncio
import sys
from concurrent import futures
from pathlib import Path
from typing import Optional

import grpc

_GENERATED_DIR = Path(__file__).resolve().parent / "generated"
if str(_GENERATED_DIR) not in sys.path:
    sys.path.insert(0, str(_GENERATED_DIR))

import video_ai_pb2 as pb2  # noqa: E402  (path injected above)
import video_ai_pb2_grpc as pb2_grpc  # noqa: E402

from backend.planner.message_orchestrator import MessageOrchestrator  # noqa: E402
from backend.session.session_manager import SessionManager  # noqa: E402
from backend.storage.db import Database  # noqa: E402

DEFAULT_ADDRESS = "127.0.0.1:50051"


class VideoAIServicer(pb2_grpc.VideoAIServiceServicer):
    """Servicer backed by the SessionManager / SQLite storage + planner pipeline."""

    def __init__(
        self,
        session_manager: SessionManager,
        orchestrator: Optional[MessageOrchestrator] = None,
    ) -> None:
        self._sessions = session_manager
        self._orchestrator = orchestrator or MessageOrchestrator(
            session_manager.db, session_manager
        )

    # ------------------------------------------------------------------ #
    def CreateSession(self, request, context):  # noqa: N802 (gRPC naming)
        session = self._sessions.create_session(title=request.title or None)
        return pb2.CreateSessionResponse(
            session_id=session["session_id"],
            created_at=session["created_at"],
        )

    # ------------------------------------------------------------------ #
    def UploadVideo(self, request, context):  # noqa: N802
        if not self._require_session(request.session_id, context):
            return pb2.UploadVideoResponse()
        if not request.video_path:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "video_path is required")
        video = self._sessions.save_video(request.session_id, request.video_path)
        return pb2.UploadVideoResponse(
            video_id=video["video_id"],
            video_path=video["video_path"],
            status="stored",
        )

    # ------------------------------------------------------------------ #
    def SendMessage(self, request, context):  # noqa: N802
        if not self._require_session(request.session_id, context):
            return pb2.SendMessageResponse()
        if not request.message:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "message is required")
            return pb2.SendMessageResponse()

        # The orchestrator + agents are async (MCP tool calls); run them to
        # completion on a dedicated event loop for this request.
        result = asyncio.run(
            self._orchestrator.handle_message(request.session_id, request.message)
        )

        files = self._sessions.db.get_generated_files(request.session_id, limit=len(result["generated_files"]) or 1) \
            if result["generated_files"] else []
        return pb2.SendMessageResponse(
            assistant_message=result["assistant_message"],
            clarification_needed=result["clarification_needed"],
            clarification_question=result["clarification_question"],
            generated_files=[
                pb2.GeneratedFile(
                    file_id=f["file_id"],
                    file_type=f["file_type"],
                    file_path=f["file_path"],
                    created_at=f["created_at"],
                )
                for f in files
            ],
        )

    # ------------------------------------------------------------------ #
    def GetChatHistory(self, request, context):  # noqa: N802
        if not self._require_session(request.session_id, context):
            return pb2.GetChatHistoryResponse()
        messages = self._sessions.get_recent_messages(
            request.session_id, request.limit
        )
        return pb2.GetChatHistoryResponse(
            messages=[
                pb2.ChatMessage(
                    message_id=m["message_id"],
                    session_id=m["session_id"],
                    role=m["role"],
                    content=m["content"],
                    created_at=m["created_at"],
                )
                for m in messages
            ]
        )

    # ------------------------------------------------------------------ #
    def _require_session(self, session_id: str, context) -> bool:
        if not session_id:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "session_id is required")
            return False
        if self._sessions.get_session(session_id) is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"session not found: {session_id}")
            return False
        return True


def create_server(
    address: str = DEFAULT_ADDRESS,
    db_path: Optional[str] = None,
    max_workers: int = 8,
) -> grpc.Server:
    """Build (but do not start) a gRPC server wired to a fresh DB connection."""
    db = Database(db_path)
    db.initialize()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    pb2_grpc.add_VideoAIServiceServicer_to_server(
        VideoAIServicer(SessionManager(db)), server
    )
    server.add_insecure_port(address)
    return server


def serve(address: str = DEFAULT_ADDRESS, db_path: Optional[str] = None) -> None:
    """Start the server and block until terminated."""
    server = create_server(address, db_path)
    server.start()
    print(f"[grpc] VideoAIService listening on {address}")
    server.wait_for_termination()
