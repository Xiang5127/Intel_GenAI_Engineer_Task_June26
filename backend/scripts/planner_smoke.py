"""Phase 7 smoke test: planner -> validator -> executor via MessageOrchestrator.

    python -m backend.scripts.planner_smoke --video "e:/Intel Task/test_folder/test_video.mp4"

Exercises the four blueprint cases:
1. "Transcribe the video"                                  -> transcription
2. "What objects are shown?"                               -> vision (objects)
3. "How many animals are in the video and export as PDF"   -> count + PDF
4. "Make a report"                                         -> clarification
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path

from backend.planner.message_orchestrator import MessageOrchestrator
from backend.planner.plan_validator import PlanValidator
from backend.planner.planner_service import PlannerService
from backend.session.session_manager import SessionManager
from backend.storage.db import Database

_T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - _T0:6.1f}s] {msg}", flush=True)


def _show_plan(query: str, has_video: bool) -> None:
    """Print the raw plan the heuristic planner emits (no execution)."""
    planner = PlannerService()
    ctx = {"current_video": {"video_id": "v1"} if has_video else None}
    raw = planner.generate_plan(query, ctx)
    plan = json.loads(raw)
    intents = [s["intent"] for s in plan["steps"]]
    log(f"  plan[{query!r}] conf={plan['confidence']} intents={intents} "
        f"clarify={plan.get('clarification_question')}")


async def _run(db: Database, video_path: str) -> None:
    sessions = SessionManager(db)
    orch = MessageOrchestrator(db, sessions)

    session = sessions.create_session(title="Phase 7 smoke")
    sid = session["session_id"]
    sessions.save_video(sid, video_path)
    log(f"setup: session={sid} video attached")

    log("plan previews (planner only):")
    for q in ("Transcribe the video", "What objects are shown?",
              "How many animals are in the video and export as PDF", "Make a report"):
        _show_plan(q, has_video=True)

    # Case 1: transcription
    log("case 1: 'Transcribe the video'")
    r1 = await orch.handle_message(sid, "Transcribe the video")
    log(f"  reply={r1['assistant_message'][:80]!r} clarify={r1['clarification_needed']}")
    assert not r1["clarification_needed"], "transcription should not clarify"

    # Case 2: object analysis
    log("case 2: 'What objects are shown?'")
    r2 = await orch.handle_message(sid, "What objects are shown?")
    log(f"  reply={r2['assistant_message'][:80]!r} clarify={r2['clarification_needed']}")
    assert not r2["clarification_needed"], "object analysis should not clarify"

    # Case 3: count + PDF
    log("case 3: 'How many animals are in the video and export as PDF'")
    r3 = await orch.handle_message(sid, "How many animals are in the video and export as PDF")
    log(f"  reply={r3['assistant_message'][:100]!r}")
    log(f"  files={[f['file_path'] for f in r3['generated_files']]}")
    assert not r3["clarification_needed"], "count+pdf should not clarify"
    assert any(f["file_type"] == "pdf" for f in r3["generated_files"]), "no PDF generated"
    for f in r3["generated_files"]:
        assert Path(f["file_path"]).exists(), f"missing file {f['file_path']}"

    # Case 4: ambiguous report -> clarification
    log("case 4: 'Make a report'")
    r4 = await orch.handle_message(sid, "Make a report")
    log(f"  clarify={r4['clarification_needed']} q={r4['clarification_question']!r}")
    assert r4["clarification_needed"], "'Make a report' should ask for clarification"
    assert sessions.get_pending_clarification(sid), "pending clarification not persisted"

    log("DONE: Phase 7 planner smoke test passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 7 planner smoke test")
    parser.add_argument("--video", required=True, help="path to a local .mp4")
    args = parser.parse_args()

    db = Database(Path("backend/storage/phase7_smoke.db"))
    if db.db_path.exists():
        db.close()
        db.db_path.unlink()
        db = Database(db.db_path)
    db.initialize()
    try:
        asyncio.run(_run(db, args.video))
    finally:
        db.close()


if __name__ == "__main__":
    main()
