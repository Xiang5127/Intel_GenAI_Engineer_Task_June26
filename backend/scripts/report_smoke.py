"""Phase 6 smoke test: Summary + Report agents end-to-end.

    python -m backend.scripts.report_smoke

Seeds stored analyses (transcript/objects/ocr/graphs), runs SummaryAgent to
build a normalized report_data/slide_data bundle, then ReportAgent to produce a
PDF + PPTX via the report MCP server, and verifies generated_files records.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
import time
from pathlib import Path

from backend.agents.report_agent import ReportAgent
from backend.agents.summary_agent import SummaryAgent
from backend.context.context_builder import ContextBuilder
from backend.mcp_clients.mcp_client_manager import MCPClientManager
from backend.services.summarization import RuleBasedSummarizer, set_summarizer
from backend.session.session_manager import SessionManager
from backend.storage.db import Database

_T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - _T0:6.1f}s] {msg}", flush=True)


def _seed_analyses(db: Database, video_id: str) -> None:
    db.save_video_analysis(video_id, "transcript", json.dumps({
        "text": "This tutorial explains git, a system for tracking changes across files. "
                "You create a repository, stage changes, and commit them.",
        "segments": [], "language": "en",
    }))
    db.save_video_analysis(video_id, "objects", json.dumps({
        "backend": "opencv-fallback", "detect_available": True,
        "label_counts": {"person": 3, "laptop": 2, "cup": 1},
        "frames_analyzed": 5,
    }))
    db.save_video_analysis(video_id, "ocr", json.dumps({
        "backend": "opencv-fallback", "ocr_available": False,
        "combined_text": "", "frames_analyzed": 5,
    }))
    db.save_video_analysis(video_id, "graphs", json.dumps({
        "frames_analyzed": 30, "graph_frame_count": 5, "contains_graphs": True, "frames": [],
    }))


async def _run(db: Database) -> None:
    sessions = SessionManager(db)
    context_builder = ContextBuilder(sessions, db)
    mcp = MCPClientManager()

    session = sessions.create_session(title="Phase 6 smoke")
    sid = session["session_id"]
    video = sessions.save_video(sid, "C:/fake/demo.mp4", duration_seconds=42.0)
    _seed_analyses(db, video["video_id"])
    log(f"setup: session={sid} video={video['video_id']} (analyses seeded)")

    context = context_builder.build(sid)

    log("step 1: SummaryAgent (rule-based) ...")
    summary_agent = SummaryAgent(mcp, db)
    s_res = await summary_agent.handle("SUMMARIZE", {}, context)
    log(f"  success={s_res.success} summary={s_res.summary!r}")
    assert s_res.success, s_res.error
    assert s_res.data["report_data"]["sections"], "no report sections"
    assert s_res.data["slide_data"]["slides"], "no slides"

    log("step 2: ReportAgent (format=both, spawns report MCP) ...")
    report_agent = ReportAgent(mcp, db)
    r_res = await report_agent.handle("GENERATE_REPORT", {"format": "both"}, context)
    log(f"  success={r_res.success} summary={r_res.summary!r}")
    assert r_res.success, r_res.error

    files = r_res.data["files"]
    assert len(files) == 2, f"expected 2 files, got {len(files)}"
    for f in files:
        p = Path(f["file_path"])
        assert p.exists() and p.stat().st_size > 0, f"missing/empty: {p}"
        log(f"  {f['file_type'].upper()} ok: {p.name} ({p.stat().st_size} bytes)")

    records = db.get_generated_files(sid)
    assert len(records) == 2, f"expected 2 generated_files records, got {len(records)}"
    log("persist: 2 generated_files records stored")

    log("DONE: Phase 6 report smoke test passed.")


def main() -> None:
    set_summarizer(RuleBasedSummarizer())
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db = Database(Path(tmp) / "phase6.db")
        db.initialize()
        try:
            asyncio.run(_run(db))
        finally:
            db.close()
            set_summarizer(None)


if __name__ == "__main__":
    main()
