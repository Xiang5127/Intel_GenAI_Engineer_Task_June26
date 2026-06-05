# Technical Reference

This document is a concise technical reference for the Intel Local Video AI MVP.
Use [`README.md`](./README.md) as the primary setup and demo guide.

## Project Summary

The application analyzes local `.mp4` videos through a desktop chat interface.
All processing runs locally using a React/Tauri frontend, a Python gRPC backend,
local MCP servers, OpenVINO, faster-whisper, Ollama, and SQLite.

## Runtime Architecture

```txt
React + Tauri UI
        |
        | Tauri commands
        v
Rust gRPC Bridge
        |
        | gRPC
        v
Python Backend
  - gRPC service
  - Session manager
  - SQLite storage
  - Context builder
  - Planner and executor
  - Agent registry
  - MCP client manager
        |
        | local stdio MCP
        v
MCP Servers
  - video_mcp_server
  - transcription_mcp_server
  - vision_mcp_server
  - report_mcp_server
```

## Message Flow

```txt
User message
  -> gRPC SendMessage
  -> persist user chat message
  -> build session context
  -> route known workflow or request local planner JSON
  -> validate and repair plan
  -> execute agent steps through local MCP tools
  -> persist analysis and generated files
  -> return assistant response
```

## gRPC Contract

Defined in `backend/proto/video_ai.proto`.

- `CreateSession(title) -> session_id, created_at`
- `UploadVideo(session_id, video_path) -> video_id, video_path, status`
- `SendMessage(session_id, message) -> assistant_message, clarification fields, generated_files`
- `GetChatHistory(session_id, limit) -> messages`

Generated Python stubs live in `backend/generated/`. The frontend does not call
MCP servers directly; it communicates through the Tauri/Rust gRPC bridge.

## SQLite Storage

Defined in `backend/storage/schema.sql`.

- `sessions`: session metadata, current video, pending clarification.
- `chat_messages`: user, assistant, and system messages.
- `videos`: uploaded/selected local video records.
- `video_analysis`: transcript, object, OCR, graph, visual, and summary results.
- `generated_files`: PDF and PowerPoint artifact records.
- `content_bundles`: reusable normalized report/slide content.

## Agents

- `TranscriptionAgent`: extracts audio, runs faster-whisper, persists transcript.
- `VisionAgent`: samples frames, runs object detection, OCR, and graph detection.
- `SummaryAgent`: builds evidence-aware summaries and normalized report data.
- `ReportAgent`: generates PDF/PPTX files from normalized content.
- `ClarificationAgent`: returns user-facing clarification prompts.

Agents run on the backend and call MCP tools through the MCP client manager.

## MCP Servers and Tools

- `video_mcp_server`
  - `get_video_metadata`
  - `extract_audio`
  - `extract_frames`
- `transcription_mcp_server`
  - `transcribe_audio`
- `vision_mcp_server`
  - `detect_objects`
  - `count_objects`
  - `run_ocr`
  - `detect_graphs`
- `report_mcp_server`
  - `generate_pdf_report`
  - `generate_pptx_report`

## Local Models and Configuration

Core defaults:

- Planner/analysis model: Ollama `qwen2.5:3b`
- Whisper model: `tiny`
- OpenVINO object model: `ssdlite_mobilenet_v2_fp16`
- OpenVINO OCR models: `horizontal-text-detection-0001`, `text-recognition-0012`

Useful environment variables:

```powershell
$env:PLANNER_BACKEND="ollama"        # or heuristic
$env:ANALYSIS_BACKEND="ollama"       # or rule_based
$env:OLLAMA_MODEL="qwen2.5:3b"
$env:ANALYSIS_MAX_TOKENS="700"
$env:WHISPER_MODEL_SIZE="tiny"
$env:VISION_MODELS_DIR="C:\path\to\repo\backend\models\openvino"
$env:VISION_DET_MODEL="C:\models\object-detection.xml"
$env:VISION_OCR_DET_MODEL="C:\models\text-detection.xml"
$env:VISION_OCR_REC_MODEL="C:\models\text-recognition.xml"
$env:VIDEO_AI_GRPC_ADDRESS="http://127.0.0.1:50051"
```

OpenVINO model files can be prepared with:

```powershell
python -m backend.scripts.setup_openvino_models
```

## Generated Artifacts

PDF and PowerPoint files are written to:

```txt
backend/outputs/reports/
```

Generated artifacts are local outputs and are not committed to the repo.

## Operating Constraints

- No cloud APIs.
- No public MCP servers.
- No vector database.
- Local models only.
- Frontend communicates with the backend through gRPC only.
- Frontend never calls MCP servers directly.
- gRPC proto, MCP boundaries, and local storage are the main integration
  contracts.

## Verification Reference

Run from the repository root:

```powershell
python -m unittest discover -s backend/tests -v
python -m backend.scripts.vision_smoke --video "test_folder/test_video.mp4"
python -m backend.scripts.interview_demo_smoke --video "test_folder/test_video.mp4"
```

For the full demo setup, use [`README.md`](./README.md).
