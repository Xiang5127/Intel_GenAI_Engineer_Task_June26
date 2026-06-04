"""Backend CLI entry point.

Run from the repository root so that the ``backend`` package is importable:

    # Phase 1 storage/session smoke test
    python -m backend.main smoke --db backend/storage/smoke.db --reset

    # gRPC server
    python -m backend.main serve --address 127.0.0.1:50051

The ``smoke`` command exercises the storage layer directly; ``serve`` starts the
gRPC server with the local planner, agents, MCP tools, and analysis pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.context.context_builder import ContextBuilder
from backend.grpc_server import DEFAULT_ADDRESS, serve
from backend.session.session_manager import SessionManager
from backend.storage.db import DEFAULT_DB_PATH, Database


def _dummy_response(user_message: str) -> str:
    """Phase 1 placeholder: real planning/execution arrives in Phase 7."""
    return f"(dummy) received your message: {user_message!r}"


def run_smoke_test(db_path: Path, reset: bool) -> None:
    if reset and db_path.exists():
        db_path.unlink()
        print(f"[reset] removed existing db at {db_path}")

    db = Database(db_path)
    db.initialize()
    print(f"[init] database ready at {db.db_path}")

    sessions = SessionManager(db)
    context_builder = ContextBuilder(sessions, db)

    # 1. create a session
    session = sessions.create_session(title="Smoke Test Session")
    session_id = session["session_id"]
    print(f"[session] created {session_id}")

    # 2. attach a dummy video (path need not exist for Phase 1)
    video = sessions.save_video(
        session_id,
        video_path=str(Path("sample_inputs/sample.mp4").resolve()),
        duration_seconds=42.0,
        width=1280,
        height=720,
        fps=30.0,
    )
    print(f"[video] stored + set current: {video['video_id']}")

    # 3. save a user message and a dummy assistant response
    user_msg = "Transcribe the video."
    sessions.save_chat_message(session_id, "user", user_msg)
    assistant_msg = _dummy_response(user_msg)
    sessions.save_chat_message(session_id, "assistant", assistant_msg)
    print(f"[chat] user -> assistant dummy exchange saved")

    # 4. reload recent messages to prove persistence round-trips
    recent = sessions.get_recent_messages(session_id, limit=10)
    print(f"[chat] {len(recent)} message(s) persisted")

    # 5. build + print context
    context = context_builder.build(session_id)
    print("[context] built:")
    print(json.dumps(context, indent=2))

    db.close()
    print("[done] Phase 1 smoke test completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Intel Local Video AI backend CLI")
    sub = parser.add_subparsers(dest="command")

    smoke = sub.add_parser("smoke", help="Phase 1 storage/session smoke test")
    smoke.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite db path (default: {DEFAULT_DB_PATH})",
    )
    smoke.add_argument(
        "--reset", action="store_true", help="delete the db file before running"
    )

    serve_p = sub.add_parser("serve", help="Phase 2 gRPC server")
    serve_p.add_argument("--address", default=DEFAULT_ADDRESS, help="host:port to bind")
    serve_p.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite db path (default: {DEFAULT_DB_PATH})",
    )

    args = parser.parse_args()

    if args.command == "serve":
        serve(args.address, str(args.db))
    elif args.command == "smoke":
        run_smoke_test(args.db, args.reset)
    else:
        # Default to the Phase 1 smoke test for backward compatibility.
        run_smoke_test(DEFAULT_DB_PATH, reset=False)


if __name__ == "__main__":
    main()
