# HANDOFF TO CODEX

This document originally handed the **Intel Local Video AI MVP** from Windsurf to Codex. The React + Tauri frontend, local LLM analysis, and interaction-reliability milestones are implemented. Phase-by-phase detail lives in `CHECKPOINTS.md`.

---

## 1. Current Project Overview
A **fully local, offline** desktop app for analyzing short `.mp4` videos through a chat interface. The user selects a local video and asks natural-language questions; the system transcribes audio, analyzes sampled frames (objects / OCR / heuristic graphs), summarizes, and generates PDF/PPTX reports — all with **local models and local MCP servers, no cloud APIs**. Chat history persists across restarts in SQLite.

## 2. Current Architecture Summary
```txt
React UI
  | Tauri commands
Rust tonic gRPC bridge
  | gRPC (proto contract)
Python Backend Host
  ├── gRPC Server (VideoAIService)     backend/grpc_server.py
  ├── SessionManager                   backend/session/session_manager.py
  ├── SQLite Storage                   backend/storage/db.py + schema.sql
  ├── ContextBuilder                   backend/context/context_builder.py
  ├── MessageOrchestrator              backend/planner/message_orchestrator.py
  │     ├── PlannerService (LLM/heuristic)   backend/planner/planner_service.py
  │     ├── PlanValidator (deterministic)    backend/planner/plan_validator.py
  │     ├── ClarificationManager             backend/planner/clarification_manager.py
  │     └── PlanExecutor (deterministic)     backend/planner/plan_executor.py
  ├── Agent Registry                   backend/agents/*
  └── MCP Client Manager               backend/mcp_clients/mcp_client_manager.py
        | MCP local stdio/process transport
Local MCP Servers                      backend/mcp_servers/*
  ├── video_mcp_server
  ├── transcription_mcp_server
  ├── vision_mcp_server
  └── report_mcp_server
        |
Local Tools / Models (OpenCV/imageio-ffmpeg, faster-whisper, OpenVINO, ReportLab/python-pptx, Ollama qwen2.5:3b, SQLite)
```

**Control flow for a user message (`SendMessage`):**
save user message -> build context -> deterministically route known workflows or ask the local planner for JSON -> repair and validate the plan -> execute via agents/MCP -> compose a concise deterministic response -> persist and reply.

## 3. What Has Already Been Implemented
- Completed milestones (see `CHECKPOINTS.md`). In short:
  - SQLite storage, sessions, chat persistence, compact context building.
  - gRPC `VideoAIService` (4 RPCs) wired to the planner pipeline.
  - Four real local MCP servers (video, transcription, vision, report).
  - Agents: transcription, vision, summary, report, clarification.
  - JSON planning pipeline: deterministic common-workflow router, Ollama `qwen2.5:3b` fallback planner, plan repair, deterministic PlanValidator and PlanExecutor.
  - PDF/PPTX report generation from a normalized data structure.
  - Evidence-aware local Ollama summaries and query-specific reports.
  - Reusable normalized content bundles for reliable repeat PDF/PPTX exports.
  - Smoke tests for every phase under `backend/scripts/`.
  - React + Tauri desktop frontend with a Rust tonic bridge, MP4 picker, chat,
    clarification display, generated-files panel, active-session resume, and tests.

## 4. What Is Incomplete
- **Frontend packaging/lifecycle:** the Python backend is started manually during development; automatic backend packaging and launch are deferred.
- **Real vision models:** detection/OCR run in **fallback mode** (no IR model bundled). Set `VISION_DET_MODEL` + an OCR backend to enable.
- **Local LLM latency:** the first uncached Ollama summary may still be slow on
  CPU. Common routing is immediate and repeated exports reuse cached content.
- **Multi-turn clarification:** a pending question is persisted, but answers are re-planned fresh (no deep stitching).
- **`extract_audio` error masking:** ffmpeg failures with empty output are reported as `has_audio=False`.
- **Submission polish:** sample outputs and final submission documentation.

## 5. How to Run the Backend
Prerequisites: Python 3.13 (project tested on it), packages from `backend/requirements.txt`, and (for LLM planning) Ollama.

```powershell
# from repo root: e:\Intel Task
python -m pip install -r backend/requirements.txt

# one-time, for the LLM planner (then fully offline):
#   install Ollama from https://ollama.com/download
ollama pull qwen2.5:3b

# start the gRPC server (default 127.0.0.1:50051)
python -m backend.main serve --address 127.0.0.1:50051
```
- To run **without** the LLM (deterministic, no Ollama needed): set `PLANNER_BACKEND=heuristic`.
- To keep LLM planning but use deterministic summaries and answers: set
  `ANALYSIS_BACKEND=rule_based`.
- Analysis uses `ANALYSIS_MODEL` and `ANALYSIS_TIMEOUT` when set, otherwise it
  inherits `OLLAMA_MODEL` and `OLLAMA_TIMEOUT`.
- `ANALYSIS_MAX_TOKENS` controls structured summary output length (default `700`).
- DB path defaults to `backend/storage/video_ai.db`; generated files go under `backend/outputs/`.

## 6. How to Run or Test MCP Servers
MCP servers are spawned automatically by `MCPClientManager` as stdio subprocesses; you normally do not start them by hand. To exercise them directly, use the smoke tests (run from repo root):

```powershell
python -m backend.scripts.video_mcp_smoke
python -m backend.scripts.transcription_smoke --video "test_folder/test_video.mp4"
python -m backend.scripts.vision_smoke        --video "test_folder/test_video.mp4"
python -m backend.scripts.report_smoke
python -m backend.scripts.planner_smoke       --video "test_folder/test_video.mp4"   # deterministic e2e
python -m backend.scripts.llm_planner_smoke                                          # LLM routing + fallback
python -m backend.scripts.llm_analysis_smoke                                         # live analysis + answer
python -m unittest discover -s backend/tests -v
python -m backend.scripts.grpc_smoke                                                 # all 4 RPCs
```

## 7. Current gRPC Proto Contract Summary
Defined in `backend/proto/video_ai.proto` (package `video_ai`, service `VideoAIService`). Generated stubs in `backend/generated/`.

- `CreateSession(CreateSessionRequest{title}) -> CreateSessionResponse{session_id, created_at}`
- `UploadVideo(UploadVideoRequest{session_id, video_path}) -> UploadVideoResponse{video_id, video_path, status}`
- `SendMessage(SendMessageRequest{session_id, message}) -> SendMessageResponse{assistant_message, clarification_needed, clarification_question, repeated GeneratedFile generated_files}`
- `GetChatHistory(GetChatHistoryRequest{session_id, limit}) -> GetChatHistoryResponse{repeated ChatMessage messages}`
- Shared: `ChatMessage{message_id, session_id, role, content, created_at}`, `GeneratedFile{file_id, file_type, file_path, created_at}`.

> If the contract changes, regenerate stubs into `backend/generated/` (flat imports; that dir is added to `sys.path`).

## 8. Current SQLite Schema Summary
Defined in `backend/storage/schema.sql`; all timestamps are unix epoch seconds.

- **sessions**(`session_id` PK, `title`, `current_video_id` FK->videos, `pending_clarification`, `created_at`, `updated_at`)
- **chat_messages**(`message_id` PK, `session_id` FK->sessions CASCADE, `role` in user/assistant/system, `content`, `created_at`)
- **videos**(`video_id` PK, `session_id` FK->sessions CASCADE, `video_path`, `duration_seconds`, `width`, `height`, `fps`, `created_at`)
- **video_analysis**(`analysis_id` PK, `video_id` FK->videos CASCADE, `analysis_type` in transcript/objects/ocr/graphs/visual_summary/summary, `result_json`, `created_at`)
- **generated_files**(`file_id` PK, `session_id` FK->sessions CASCADE, `video_id` FK->videos SET NULL, `file_type`, `file_path`, `created_at`)
- **content_bundles**(`bundle_id` PK, `session_id` FK->sessions CASCADE, nullable `video_id`, `source_kind`, `query`, normalized `bundle_json`, `created_at`)
- Indexes on session/video lookups for messages, videos, analyses, generated files, and content bundles.

## 9. Agent List and Responsibilities
Agents live in `backend/agents/`; all extend `BaseAgent` and return an `AgentResult`. They orchestrate MCP tool calls and persist results — they never talk to the frontend.

- **TranscriptionAgent** — extract audio -> transcribe (faster-whisper) -> cache/persist `transcript`. Intent: `TRANSCRIBE_VIDEO`.
- **VisionAgent** — sample frames -> object detection / counting / OCR / graph detection -> persist `objects`/`ocr`/`graphs`. Intents: `ANALYZE_OBJECTS`, `COUNT_OBJECTS`, `ANALYZE_OCR`, `DETECT_GRAPHS`.
- **SummaryAgent** — build normalized evidence-aware `report_data`/`slide_data`
  via local Ollama, with deterministic fallback. Intents: `SUMMARIZE_VIDEO`,
  `SUMMARIZE_CHAT_HISTORY`.
- **ReportAgent** — consume normalized data -> generate PDF/PPTX via the report MCP -> record generated files. Intents: `GENERATE_PDF`, `GENERATE_PPTX`.
- **ClarificationAgent** — surface a clarification question. Intent: `CLARIFY`.

## 10. MCP Server List and Exposed Tools
Servers live in `backend/mcp_servers/` (FastMCP over stdio). Registered in `backend/mcp_clients/mcp_client_manager.py`.

- **video_mcp_server** — `get_video_metadata`, `extract_audio`, `extract_frames`
- **transcription_mcp_server** — `transcribe_audio`
- **vision_mcp_server** — `detect_objects`, `count_objects`, `run_ocr`, `detect_graphs`
- **report_mcp_server** — `generate_pdf_report`, `generate_pptx_report`

> Note: servers that load native ML libs use a `_protect_stdio()` guard and warm models on the main thread to keep the JSON-RPC stdio channel clean and avoid deadlocks.

## 11. Important Constraints (must be preserved)
- **No cloud APIs.** Everything runs locally.
- **Local models only** (faster-whisper, OpenVINO/OpenCV, Ollama `qwen2.5:3b`).
- **Actual local MCP servers** (real FastMCP stdio processes — not stubs).
- **Planner outputs JSON execution plans** matching `backend/planner/plan_schema.py`.
- **`PlanValidator` and `PlanExecutor` are deterministic code** — no LLM in validation or execution.
- **Frontend must be React + Tauri.**
- **Frontend communicates with the backend only through gRPC.**
- **Frontend must NOT call MCP servers directly** — all tool access goes through agents on the backend.

## 12. Recommended Next Work

- Exercise the completed frontend against representative videos and planner flows.
- Integrate required real OpenVINO object detection and OCR behind the existing
  runtime/service/MCP/agent boundaries.
- Add sample outputs and final submission documentation.

---

### Quick verification
Run `python -m backend.scripts.grpc_smoke` and `python -m backend.scripts.planner_smoke --video "test_folder/test_video.mp4"` to confirm the backend is healthy, then build the frontend against the gRPC contract in Section 7.
