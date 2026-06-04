# CHECKPOINTS

Per-phase status of the **Intel Local Video AI MVP** backend. All work to date is backend-only; the React + Tauri frontend (Phase 8) is **not started**. See `HANDOFF_TO_CODEX.md` for the forward plan.

All commands assume the repository root `e:\Intel Task` and that the `backend` package is importable (run from root). A test video lives at `test_folder/test_video.mp4`.

---

## Phase 0 — Project Skeleton
- **Status:** Completed
- **Commit:** `b66f60b`
- **Summary:** Established the repository structure, gRPC proto contract, SQLite schema, output folders, and the initial README from the blueprint.
- **Files/folders created or modified:**
  - `README.md`
  - `backend/proto/video_ai.proto`
  - `backend/storage/schema.sql`
  - `backend/outputs/{audio,frames,reports,analysis_json}/`
  - Package skeleton: `backend/{__init__.py, storage/, session/, context/, services/, runtimes/, mcp_servers/, mcp_clients/, agents/, planner/}`
- **How to manually test:**
  - Confirm structure exists: `dir backend` (PowerShell) shows the package folders above.
  - `python -c "import ast; ast.parse(open('backend/proto/video_ai.proto').read())"` is NOT applicable; instead just verify `backend/proto/video_ai.proto` and `backend/storage/schema.sql` open and read.
- **Known issues / limitations:**
  - No runnable code yet; skeleton only. Setup sections of README were placeholders.

---

## Phase 1 — Backend Storage / Session / Context
- **Status:** Completed
- **Commit:** `26ba72d`
- **Summary:** Implemented the SQLite storage layer (`Database`), the `SessionManager` over it, and the `ContextBuilder` that assembles a compact planner context. Added a Phase 1 CLI smoke test.
- **Files/folders created or modified:**
  - `backend/storage/db.py`
  - `backend/session/session_manager.py`
  - `backend/context/context_builder.py`
  - `backend/main.py` (CLI `smoke` subcommand)
- **How to manually test:**
  - `python -m backend.main smoke --db backend/storage/smoke.db --reset`
  - Expect: session created, dummy video attached, a user/assistant exchange persisted, recent messages reloaded, and a printed context JSON ending with `Phase 1 smoke test completed successfully.`
- **Known issues / limitations:**
  - Single shared SQLite connection guarded by a lock (fine for MVP scale; not tuned for high concurrency).

---

## Phase 2 — gRPC Skeleton
- **Status:** Completed
- **Commit:** `cebaac1`
- **Summary:** Stood up the `VideoAIService` gRPC server implementing `CreateSession`, `UploadVideo`, `SendMessage` (dummy at the time), and `GetChatHistory` over the Phase 1 storage. Generated stubs live in `backend/generated/`.
- **Files/folders created or modified:**
  - `backend/grpc_server.py`
  - `backend/generated/video_ai_pb2.py`, `backend/generated/video_ai_pb2_grpc.py`
  - `backend/main.py` (`serve` subcommand)
  - `backend/scripts/grpc_smoke.py`
- **How to manually test:**
  - End-to-end RPC test: `python -m backend.scripts.grpc_smoke`
  - Or run the server: `python -m backend.main serve --address 127.0.0.1:50051`
  - Expect: all four RPCs exercised successfully (CreateSession -> UploadVideo -> SendMessage -> GetChatHistory).
- **Known issues / limitations:**
  - Required `check_same_thread=False` + `RLock` on the DB because gRPC dispatches handlers on worker threads.
  - `SendMessage` originally returned a dummy response; replaced by the planner pipeline in Phase 7.

---

## Phase 3 — Video MCP Server
- **Status:** Completed
- **Commit:** `48321d5`
- **Summary:** First **real local MCP server** (FastMCP over stdio) exposing video metadata, audio extraction, and frame sampling. Backed by OpenCV + `imageio-ffmpeg`. Added the `MCPClientManager` that spawns/connects MCP servers as subprocesses.
- **Files/folders created or modified:**
  - `backend/services/video_processing.py`
  - `backend/mcp_servers/video_mcp_server.py`
  - `backend/mcp_clients/mcp_client_manager.py`
  - `backend/scripts/video_mcp_smoke.py`
- **Exposed tools:** `get_video_metadata`, `extract_audio`, `extract_frames`
- **How to manually test:**
  - `python -m backend.scripts.video_mcp_smoke`
  - Expect: a synthetic clip is generated, metadata returned, audio probe and frame extraction succeed (frames saved under `backend/outputs/frames/`).
- **Known issues / limitations:**
  - `extract_audio` treats any ffmpeg failure with empty output as `has_audio=False` (masks real ffmpeg errors). Tracked for a later fix.

---

## Phase 4 — Transcription MCP + Agent
- **Status:** Completed
- **Commit:** `61f7272`
- **Summary:** Local speech-to-text via **faster-whisper** behind a transcription MCP server, plus a `TranscriptionAgent` that orchestrates audio extraction -> transcription, caches results, and persists them.
- **Files/folders created or modified:**
  - `backend/runtimes/whisper_runtime.py`
  - `backend/services/speech_to_text.py`
  - `backend/mcp_servers/transcription_mcp_server.py`
  - `backend/agents/base_agent.py`, `backend/agents/transcription_agent.py`
  - `backend/scripts/transcription_smoke.py`
- **Exposed tools:** `transcribe_audio`
- **Models / env:** `WHISPER_MODEL_SIZE` (default `tiny`), `WHISPER_COMPUTE_TYPE` (default `int8`). Model downloaded once, then offline (`HF_HUB_OFFLINE=1`).
- **How to manually test:**
  - `python -m backend.scripts.transcription_smoke --video "test_folder/test_video.mp4"`
  - Expect: audio extracted, transcript text + segments returned and persisted as `transcript` analysis.
- **Known issues / limitations:**
  - Native ML libs (ctranslate2 / onnxruntime / av) write to stdout and can deadlock if initialized off the main thread. Mitigated by `_protect_stdio()` (fd-level stdout redirect) and warming the model on the **main thread** at server startup.
  - First run requires internet to download the Whisper model.

---

## Phase 5 — Vision MCP + Agent
- **Status:** Completed (fallback detection/OCR)
- **Commit:** `3b1249b`
- **Summary:** Vision MCP server exposing object detection, object counting, OCR, and heuristic graph detection, with an OpenVINO abstraction and OpenCV fallbacks. `VisionAgent` samples frames and runs the analyses, persisting `objects` / `ocr` / `graphs` results.
- **Files/folders created or modified:**
  - `backend/services/vision_analysis.py`, `backend/services/graph_detection.py`
  - `backend/mcp_servers/vision_mcp_server.py`
  - `backend/agents/vision_agent.py`
  - `backend/scripts/vision_smoke.py`
- **Exposed tools:** `detect_objects`, `count_objects`, `run_ocr`, `detect_graphs`
- **Models / env:** `VISION_DET_MODEL` (path to an OpenVINO IR `.xml` to enable real detection). OCR backend optional.
- **How to manually test:**
  - `python -m backend.scripts.vision_smoke --video "test_folder/test_video.mp4"`
  - Expect: frames sampled, detection/OCR/graph results returned (in fallback mode, detection/OCR report "unavailable" while graph heuristic still runs).
- **Known issues / limitations:**
  - **No IR model bundled** -> detection and OCR currently run in fallback mode only (no real labels). Provide `VISION_DET_MODEL` and an OCR backend to enable.
  - Graph detection is heuristic, not a trained classifier.

---

## Phase 6 — Report MCP + Summary/Report Agents
- **Status:** Completed (rule-based summarization)
- **Commit:** `c41076a`
- **Summary:** Report generation via **ReportLab (PDF)** and **python-pptx (PPTX)**, fed by a normalized `report_data` / `slide_data` structure. `SummaryAgent` builds the normalized structure using a `Summarizer` interface (currently `RuleBasedSummarizer`); `ReportAgent` consumes it and generates files, independent of how the summary was produced.
- **Files/folders created or modified:**
  - `backend/services/summarization.py` (Summarizer interface + RuleBasedSummarizer)
  - `backend/services/report_generator.py`
  - `backend/mcp_servers/report_mcp_server.py`
  - `backend/agents/summary_agent.py`, `backend/agents/report_agent.py`
  - `backend/scripts/report_smoke.py`
- **Exposed tools:** `generate_pdf_report`, `generate_pptx_report`
- **How to manually test:**
  - `python -m backend.scripts.report_smoke`
  - Expect: a PDF and PPTX produced under `backend/outputs/reports/` and recorded as generated files.
- **Known issues / limitations:**
  - Summarization is **rule-based**, not LLM. Interface is in place for a future `LLMSummarizer`.
  - TODO markers exist for Phase 7+: LLM-based summary, evidence-aware summary (transcript + OCR + objects), user-query-based reports.

---

## Phase 7 — Planner / Validator / Executor
- **Status:** Completed
- **Commits:** `6369cb0` (deterministic heuristic planner) -> `d5165fc` (local LLM planner via Ollama)
- **Summary:** Implemented the JSON planning pipeline. The planner produces a JSON execution plan; `PlanValidator` (Pydantic + rules) checks it; `PlanExecutor` runs steps deterministically through the agent registry; `MessageOrchestrator` ties it into `SendMessage`. The planner is a swappable `PlannerModel`: **Ollama `qwen2.5:3b`** is the default, with an automatic **heuristic fallback** when Ollama is unreachable.
- **Files/folders created or modified:**
  - `backend/planner/plan_schema.py`, `backend/planner/planner_prompt.py`
  - `backend/planner/planner_service.py`, `backend/planner/ollama_planner_model.py`
  - `backend/planner/plan_validator.py`, `backend/planner/clarification_manager.py`
  - `backend/planner/plan_executor.py`, `backend/planner/message_orchestrator.py`
  - `backend/agents/clarification_agent.py`
  - `backend/grpc_server.py` (wired `SendMessage` to the orchestrator)
  - `backend/session/session_manager.py` (public `db` property)
  - `backend/scripts/planner_smoke.py`, `backend/scripts/llm_planner_smoke.py`
- **Env:** `PLANNER_BACKEND` (`ollama` default | `heuristic`), `OLLAMA_HOST` (`http://localhost:11434`), `OLLAMA_MODEL` (`qwen2.5:3b`), `OLLAMA_TIMEOUT` (`120`).
- **How to manually test:**
  - One-time: install Ollama + `ollama pull qwen2.5:3b`.
  - LLM routing + fallback: `python -m backend.scripts.llm_planner_smoke` (skips the LLM portion cleanly if Ollama is down; the fallback test always runs).
  - Deterministic end-to-end execution: `python -m backend.scripts.planner_smoke --video "test_folder/test_video.mp4"` (pinned to the heuristic planner). Validates the 4 blueprint cases: transcribe, object analysis, count + PDF, and "Make a report" -> clarification.
- **Known issues / limitations:**
  - LLM plans vary even at `temperature=0`; tests assert the expected intent is **present**, not strictly first.
  - First request after a cold start is slow (model load), hence the 120s default timeout.
  - `SUMMARIZE_CHAT_HISTORY` intent is routed but the summary itself is still rule-based.
  - Multi-turn clarification stitching is minimal (a pending question is persisted; the next message is planned fresh).
