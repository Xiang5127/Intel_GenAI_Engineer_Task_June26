"""Code-first interview MVP smoke flow.

    python -m backend.scripts.interview_demo_smoke --video "test_folder/test_video.mp4"

Runs the core demo sequence through MessageOrchestrator without changing gRPC,
MCP, or frontend contracts:
objects -> count -> OCR -> summary+PDF -> PPTX reuse.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import tempfile
import time
from pathlib import Path

from backend.planner.message_orchestrator import MessageOrchestrator
from backend.planner.planner_service import HeuristicPlannerModel, PlannerService
from backend.services.summarization import RuleBasedSummarizer, set_summarizer
from backend.session.session_manager import SessionManager
from backend.storage.db import Database

_T0 = time.time()


def log(message: str) -> None:
    print(f"[{time.time() - _T0:6.1f}s] {message}", flush=True)


async def _send(orch: MessageOrchestrator, session_id: str, message: str) -> dict:
    log(f"user: {message}")
    result = await orch.handle_message(session_id, message)
    log(f"  assistant: {result['assistant_message'][:180]!r}")
    if result["clarification_needed"]:
        raise AssertionError(f"unexpected clarification: {result['clarification_question']}")
    return result


async def _run(db: Database, video_path: str) -> None:
    sessions = SessionManager(db)
    planner = PlannerService(model=HeuristicPlannerModel(), enable_fallback=False)
    orch = MessageOrchestrator(db, sessions, planner=planner)
    session = sessions.create_session(title="Interview MVP smoke")
    video = sessions.save_video(session["session_id"], video_path)
    log(f"setup: session={session['session_id']} video={video['video_id']}")

    await _send(orch, session["session_id"], "What objects are shown?")
    await _send(orch, session["session_id"], "How many people are in the video?")
    await _send(orch, session["session_id"], "Read the on-screen text using OCR.")
    pdf = await _send(
        orch,
        session["session_id"],
        "Summarize the video and generate a PDF with the key points.",
    )
    pptx = await _send(orch, session["session_id"], "Generate a PowerPoint.")

    assert any(item["file_type"] == "pdf" for item in pdf["generated_files"]), "PDF not generated"
    assert any(item["file_type"] == "pptx" for item in pptx["generated_files"]), "PPTX not generated"
    for item in [*pdf["generated_files"], *pptx["generated_files"]]:
        assert Path(item["file_path"]).exists(), f"missing generated file: {item['file_path']}"
    log("DONE: interview MVP smoke flow passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Interview MVP smoke flow")
    parser.add_argument("--video", required=True, help="path to a local .mp4")
    args = parser.parse_args()

    os.environ.setdefault("ANALYSIS_BACKEND", "rule_based")
    set_summarizer(RuleBasedSummarizer())
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(Path(tmp) / "interview_demo.db")
        db.initialize()
        try:
            asyncio.run(_run(db, args.video))
        finally:
            db.close()
            set_summarizer(None)


if __name__ == "__main__":
    main()
