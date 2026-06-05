# Intel Local Video AI Desktop App

A **fully local, offline** AI desktop application for analyzing short `.mp4` videos through a chat interface. No cloud APIs, no public MCP servers, no vector DB.

> **Current status:** The desktop frontend, local LLM analysis, and interaction-reliability milestone are implemented. The next major milestone is real OpenVINO object detection and OCR.
> - **[`HANDOFF_TO_CODEX.md`](./HANDOFF_TO_CODEX.md)** — architecture, how to run, gRPC/DB contracts, agents/MCP tools, constraints, and what to build next.
> - **[`CHECKPOINTS.md`](./CHECKPOINTS.md)** — per-phase status, files touched, manual test steps, and known limitations.

## What it will do

- Select a local `.mp4` video.
- Ask natural-language questions about it.
- Transcribe audio (local Whisper / faster-whisper).
- Analyze sampled frames (objects / OCR / heuristic graph detection, OpenVINO where feasible).
- Generate PDF and PowerPoint reports.
- Persist chat history across restarts.

## Architecture

```txt
React UI
  | Tauri commands
Rust tonic gRPC bridge
  | gRPC (proto contract)
Python Backend Host
  ├── gRPC Server          (thin API boundary)
  ├── SessionManager        (session / current video / pending clarification)
  ├── SQLite Storage        (sessions, chat, videos, analysis, generated files)
  ├── ContextBuilder        (compact planner context)
  ├── PlannerService        (deterministic routes + local LLM JSON fallback)
  ├── PlanValidator         (deterministic, Pydantic)
  ├── ClarificationManager  (elicitation questions)
  ├── PlanExecutor          (deterministic step runner)
  ├── Agent Registry        (transcription / vision / summary / report)
  └── MCP Client Manager    (spawns / connects local MCP servers)
        | MCP local stdio/process transport
Local MCP Servers
  ├── video_mcp_server
  ├── transcription_mcp_server
  ├── vision_mcp_server
  └── report_mcp_server
        |
Local Tools / Models (ffmpeg/OpenCV, Whisper, OpenVINO, OCR, ReportLab/python-pptx, SQLite)
```

## Repository layout

```txt
.
├── backend/
│   ├── proto/video_ai.proto        # gRPC contract (CreateSession, UploadVideo, SendMessage, GetChatHistory)
│   ├── storage/schema.sql          # SQLite schema
│   ├── storage/                    # db access (Phase 1)
│   ├── session/                    # SessionManager (Phase 1)
│   ├── context/                    # ContextBuilder (Phase 1)
│   ├── services/                   # tool-backing logic (Phase 3+)
│   ├── runtimes/                   # local model runtimes (Phase 4+)
│   ├── mcp_servers/                # local MCP servers (Phase 3+)
│   ├── mcp_clients/                # MCP client manager (Phase 3+)
│   ├── agents/                     # agents (Phase 4+)
│   ├── planner/                    # planner / validator / executor (Phase 7)
│   ├── outputs/{audio,frames,reports,analysis_json}/
│   └── requirements.txt
└── frontend/                       # React + Tauri app (Phase 8)
```

## Phases (per `intel_video_ai_windsurf_blueprint/05_PHASE_PROMPTS.md`)

0. **Skeleton (this phase)** — structure, proto, schema, outputs, README.
1. Storage + Session + ContextBuilder + CLI smoke test.
2. gRPC server and persisted chat/session transport.
3. Video MCP server (metadata / audio / frames).
4. Transcription MCP + agent (local Whisper).
5. Vision MCP + agent (objects / OCR / graphs, OpenVINO).
6. Report MCP + summary/report agents (PDF / PPTX).
7. Planner / Validator / Executor (JSON plan pipeline).
8. React + Tauri frontend. **Implemented.**
9. Real local LLM analysis. **Implemented.**
10. Interaction reliability and response speed. **Implemented.**

## Setup

### Prerequisites
- Python 3.x
- Node.js 20+
- Rust stable, Microsoft C++ Build Tools, and Edge WebView2
- ffmpeg — preferred for Phase 3 (fallback: OpenCV / `imageio-ffmpeg`)

### Run backend
See **[`HANDOFF_TO_CODEX.md` §5](./HANDOFF_TO_CODEX.md)** for full setup. Quick start (from repo root):
```powershell
python -m pip install -r backend/requirements.txt
ollama pull qwen2.5:3b          # one-time; or set PLANNER_BACKEND=heuristic to skip the LLM
python -m backend.main serve --address 127.0.0.1:50051
```

Ollama produces evidence-aware summaries, query-specific reports, and
chat-history summaries. Common workflows are routed deterministically, and
completed plans use short deterministic responses instead of a second LLM call.
To use deterministic analysis output too, set `ANALYSIS_BACKEND=rule_based`.

Optional analysis overrides:
```powershell
$env:ANALYSIS_MODEL="qwen2.5:3b"  # defaults to OLLAMA_MODEL
$env:ANALYSIS_TIMEOUT="120"       # defaults to OLLAMA_TIMEOUT
$env:ANALYSIS_MAX_TOKENS="700"    # structured summary generation cap
```

### Verify backend
```powershell
python -m unittest discover -s backend/tests -v
python -m backend.scripts.llm_planner_smoke
python -m backend.scripts.llm_analysis_smoke
python -m backend.scripts.report_smoke
```

### Quick end-to-end test

From the repository root, install dependencies and prepare the local model once:
```powershell
python -m pip install -r backend/requirements.txt
ollama pull qwen2.5:3b
```

Make sure Ollama is running, then start the backend:
```powershell
python -m backend.main serve --address 127.0.0.1:50051
```

Keep that terminal open. In a second terminal, start the desktop frontend:
```powershell
cd frontend
npm install
npm run tauri dev
```

In the app:
1. Select `test_folder/test_video.mp4`.
2. Send `Summarize the video`.
3. Send `What is the main point?`.
4. Send `Create a PDF report with the key points`.
5. Send `Generate a PowerPoint`.
6. Confirm the PowerPoint reuses the latest report content without trying to read the PDF.
7. Send `Summarize our discussion so far and generate a PDF`.
8. Confirm both generated files appear and open from the files panel.

The first uncached Ollama summary can still be slow on CPU. Repeated exports
reuse the latest normalized content bundle and require no new LLM call.
Generated PDF/PPTX files are outputs only and are never treated as evidence.

For deterministic testing without Ollama analysis:
```powershell
$env:PLANNER_BACKEND="heuristic"
$env:ANALYSIS_BACKEND="rule_based"
python -m backend.main serve --address 127.0.0.1:50051
```

Stop the backend or frontend with `Ctrl+C`.

### Run frontend
Start the backend first, then in another terminal:
```powershell
cd frontend
npm install
npm run tauri dev
```

See [`frontend/README.md`](./frontend/README.md) for architecture, verification,
session persistence, endpoint configuration, and troubleshooting.

## Example queries
```txt
Transcribe the video.
Summarize the video.
What objects are shown in the video?
Are there any graphs in the video?
Create a PowerPoint with the key points.
Summarize our discussion so far and generate a PDF.
How many animals are in the video and export as PDF.
Make a report.            # -> should ask a clarification
```

## Constraints
- All AI inference runs **locally** (Whisper / OpenVINO / Ollama).
- No cloud APIs, no public MCP servers, no vector DB, no LangChain/LangGraph, no real-time streaming.
- Generated files are stored under `backend/outputs/`.
