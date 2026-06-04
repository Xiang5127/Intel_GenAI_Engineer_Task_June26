# Implementation Order

Build in vertical slices. Do not build the entire architecture in one giant pass.

## Phase 0 — Repository Skeleton

Goal:
Create project structure, configs, and README placeholders.

Deliverables:
- `/frontend`
- `/backend`
- `/backend/proto/video_ai.proto`
- `/backend/storage/schema.sql`
- `/backend/outputs`
- root README

Do not implement AI yet.

---

## Phase 1 — Backend Core Without AI

Goal:
Make backend store sessions, videos, chat messages, and return simple responses.

Implement:
- SQLite schema
- SessionManager
- Storage functions
- ContextBuilder basic version
- gRPC service skeleton
- CLI/dev test script

Expected result:
- Can create session.
- Can upload video path.
- Can save/load chat messages.
- Can return dummy response.

---

## Phase 2 — Video Processing MCP Server

Goal:
Implement first actual MCP server.

Implement:
- `video_mcp_server.py`
- Tools:
  - `get_video_metadata`
  - `extract_audio`
  - `extract_frames`

Use:
- ffmpeg/moviepy/OpenCV, whichever is fastest to implement.

Expected result:
- Given MP4 path, output audio file and sampled frames.

---

## Phase 3 — Transcription MCP Server + Agent

Goal:
Turn audio into transcript.

Implement:
- `transcription_mcp_server.py`
- Tool:
  - `transcribe_audio`
- `TranscriptionAgent`
- Cache transcript in SQLite.

Use:
- Whisper tiny/base or faster-whisper.
- Local only.

Expected result:
- Query "Transcribe the video" returns transcript.

---

## Phase 4 — Vision MCP Server + Agent

Goal:
Analyze video frames.

Implement:
- `vision_mcp_server.py`
- Tools:
  - `detect_objects`
  - `count_objects`
  - `run_ocr`
  - `detect_graphs`
- `VisionAgent`

Use:
- OpenVINO vision runtime if possible.
- Otherwise implement basic frame-level analysis first, then plug OpenVINO.
- OCR/graph detection can be heuristic-based.

Expected result:
- Query "What objects are shown?" returns objects.
- Query "Are there graphs?" returns graph candidates.

---

## Phase 5 — Report MCP Server + Agent

Goal:
Generate PDF and PPTX files.

Implement:
- `report_mcp_server.py`
- Tools:
  - `generate_pdf_report`
  - `generate_pptx_report`
- `ReportAgent`
- `SummaryAgent` simple version

Use:
- ReportLab/fpdf2
- python-pptx

Expected result:
- Query "Generate a PDF report" creates PDF.
- Query "Create PowerPoint" creates PPTX.

---

## Phase 6 — Planner JSON Plan

Goal:
Replace hardcoded routing with JSON planning.

Implement:
- `planner/plan_schema.py`
- `planner/planner_service.py`
- `planner/plan_validator.py`
- `planner/clarification_manager.py`
- `planner/plan_executor.py`

Planner can initially be stubbed/rule-based, but architecture must support local LLM.

Expected result:
- Multi-step query works:
  "How many animals are in the video and export as PDF."
  → vision step
  → report step

---

## Phase 7 — Frontend

Goal:
Build usable React + Tauri UI.

Implement:
- Video picker.
- Chat UI.
- Generated file panel.
- gRPC client.
- Chat history load.

Expected result:
- End-to-end desktop app works.

---

## Phase 8 — Polish

Goal:
Prepare submission.

Deliver:
- README setup guide
- architecture diagram
- sample input video
- sample transcript
- sample PDF
- sample PPTX
- limitations.md
- demo script

Do not add major features in this phase.
