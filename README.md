# Intel Local Video AI Desktop App

A fully local desktop application for analyzing `.mp4` videos through a chat
interface. The app uses a React/Tauri frontend, a Python gRPC backend, local MCP
servers, OpenVINO, faster-whisper, Ollama, and SQLite. No cloud APIs are used.

## Application Screenshot

![Application Screenshot](./Application%20Screenshot.jpeg)

## What It Does

- Select and upload a local `.mp4` video.
- Ask natural-language questions about the video.
- Transcribe speech with a local Whisper model.
- Detect objects with OpenVINO.
- Read on-screen text with OpenVINO OCR.
- Detect chart-like visuals with OpenCV heuristics.
- Summarize video content and chat history.
- Generate PDF and PowerPoint reports.
- Persist sessions and chat history locally.

## Architecture

```txt
React + Tauri Desktop UI
        |
        | Tauri commands
        v
Rust gRPC Bridge (tonic)
        |
        | gRPC: backend/proto/video_ai.proto
        v
Python Backend
  - gRPC API
  - Session and SQLite storage
  - Planner and agent executor
  - Local MCP client manager
        |
        | local stdio MCP
        v
Local MCP Servers
  - Video tools: metadata, audio extraction, frame sampling
  - Transcription tools: faster-whisper
  - Vision tools: OpenVINO object detection, OCR, OpenCV graph heuristics
  - Report tools: PDF and PowerPoint generation
        |
        v
Local Models and Artifacts
  - OpenVINO IR models
  - Ollama qwen2.5:3b
  - SQLite database
  - Generated PDFs and PPTX files
```

## Folder Structure

```txt
frontend/                    React + Tauri desktop app
backend/proto/               gRPC contract
backend/grpc_server.py       Python gRPC service
backend/agents/              Transcription, vision, summary, report agents
backend/mcp_servers/         Local FastMCP servers
backend/services/            Video, vision, summary, report logic
backend/runtimes/            Local model runtime wrappers
backend/storage/             SQLite schema and database access
backend/outputs/reports/     Generated PDF and PowerPoint files
test_folder/                 Sample input videos
```

## Implemented Features

| Component | Implementation |
| --- | --- |
| Frontend | React + TypeScript + Tauri desktop UI |
| Desktop bridge | Rust `tonic` gRPC client |
| Backend API | Python gRPC service |
| Video processing | OpenCV + imageio/ffmpeg |
| Transcription | faster-whisper, default `tiny`, local model |
| Vision | OpenVINO object detection + OpenVINO OCR, with OpenCV fallback |
| Local LLM | Ollama `qwen2.5:3b`, with deterministic fallback |
| Reports | ReportLab PDF and python-pptx PowerPoint generation |
| Storage | SQLite sessions, chat, analysis, generated files |
| MCP | Local FastMCP stdio servers for video, transcription, vision, reports |

## Known Limitations and Future Improvements

Known limitations:

- The backend is started manually for the MVP demo.
- The first local LLM request can be slow on CPU.
- Object detection and OCR quality depend on the selected OpenVINO models.
- Chart detection is heuristic, not a trained chart classifier.
- There is no installer or packaged backend launcher yet.
- The frontend resumes one active session; there is no session browser.

With more time, the app could be extended with:

- Automatic backend startup from Tauri.
- A model management UI for local OpenVINO and Ollama models.
- Stronger multi-turn clarification handling.
- Richer PDF and PowerPoint templates.
- Domain-specific OpenVINO models for more accurate detection.
- Progress indicators for long-running analysis steps.

## Quick Setup

Use two command prompts:

- **Command Prompt 1:** backend gRPC server.
- **Command Prompt 2:** frontend Tauri app.

One-time setup from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
ollama pull qwen2.5:3b
python -m backend.scripts.setup_openvino_models
```

Make sure Ollama is running before starting the backend.

Command Prompt 1, from the repository root:

```powershell
python -m backend.main serve --address 127.0.0.1:50051
```

Keep Command Prompt 1 open.

Command Prompt 2:

```powershell
cd frontend
npm install
npm run tauri dev
```

For deterministic testing without Ollama analysis:

```powershell
$env:PLANNER_BACKEND="heuristic"
$env:ANALYSIS_BACKEND="rule_based"
python -m backend.main serve --address 127.0.0.1:50051
```

## End-to-End Demo Test

Use `test_folder/test_video.mp4` as the sample video.

Try these five queries:

```txt
What objects are shown in the video? Describe them.
Read the on-screen text using OCR.
Transcribe the video.
Summarize the video.
Generate a PDF report with the key points from the video.
```

Optional follow-up:

```txt
Generate a PowerPoint from the latest report content.
```

## Sample Inputs and Generated Artifacts

Sample inputs are stored in [`test_folder/`](./test_folder/).

Generated PDFs and PowerPoints are written to
[`backend/outputs/reports/`](./backend/outputs/reports/).

Generated artifacts are local demo outputs and are not committed to the repo.
Run the demo queries to recreate fresh files.

## Verification

```powershell
python -m unittest discover -s backend/tests -v
python -m backend.scripts.vision_smoke --video "test_folder/test_video.mp4"
python -m backend.scripts.interview_demo_smoke --video "test_folder/test_video.mp4"
```

## Local-Only Constraints

- No cloud APIs.
- No frontend access to MCP servers.
- The frontend talks to the backend through gRPC only.
- Generated files remain local under `backend/outputs/reports/`.
