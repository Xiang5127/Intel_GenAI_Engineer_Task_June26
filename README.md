# Intel Local Video AI Desktop App

A **fully local, offline** AI desktop application for analyzing short `.mp4` videos through a chat interface. No cloud APIs, no public MCP servers, no vector DB.

## What it will do

- Select a local `.mp4` video.
- Ask natural-language questions about it.
- Transcribe audio (local Whisper / faster-whisper).
- Analyze sampled frames (objects / OCR / heuristic graph detection, OpenVINO where feasible).
- Generate PDF and PowerPoint reports.
- Persist chat history across restarts.

## Architecture

```txt
React + Tauri Frontend
  | gRPC (proto contract)
Python Backend Host
  ├── gRPC Server          (thin API boundary)
  ├── SessionManager        (session / current video / pending clarification)
  ├── SQLite Storage        (sessions, chat, videos, analysis, generated files)
  ├── ContextBuilder        (compact planner context)
  ├── PlannerService        (local LLM -> JSON plan)
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
2. gRPC server skeleton (dummy SendMessage).
3. Video MCP server (metadata / audio / frames).
4. Transcription MCP + agent (local Whisper).
5. Vision MCP + agent (objects / OCR / graphs, OpenVINO).
6. Report MCP + summary/report agents (PDF / PPTX).
7. Planner / Validator / Executor (JSON plan pipeline).
8. React + Tauri frontend.
9. Docs + sample outputs.

## Setup

> TODO — filled in as phases land.

### Prerequisites
- Python 3.x (installed)
- Node.js (installed)
- Rust + Tauri toolchain — **needed for Phase 8 (not yet installed)**
- ffmpeg — preferred for Phase 3 (fallback: OpenCV / `imageio-ffmpeg`)

### Run backend
> TODO (Phase 1+)

### Run frontend
> TODO (Phase 8)

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
- All AI inference runs **locally** (Hugging Face / OpenVINO).
- No cloud APIs, no public MCP servers, no vector DB, no LangChain/LangGraph, no real-time streaming.
- Generated files are stored under `backend/outputs/`.
