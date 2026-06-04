# Architecture Blueprint

## High-Level Architecture

```txt
React + Tauri Frontend
  ↓ gRPC
Python Backend Host
  ├── gRPC Server
  ├── SessionManager
  ├── SQLite Storage
  ├── ContextBuilder
  ├── PlannerService
  ├── PlanValidator
  ├── ClarificationManager
  ├── PlanExecutor
  ├── Agent Registry
  └── MCP Client Manager
       ↓ MCP local stdio/process transport
Local MCP Servers
  ├── video_mcp_server
  ├── transcription_mcp_server
  ├── vision_mcp_server
  └── report_mcp_server
       ↓
Local Tools / Models / Libraries
  ├── ffmpeg / OpenCV
  ├── Whisper / faster-whisper / HF
  ├── OpenVINO vision runtime
  ├── OCR
  ├── ReportLab / python-pptx
  └── SQLite
```

## Component Responsibilities

### Frontend
- Display chat UI.
- Select local MP4.
- Send user messages to backend.
- Display responses, clarifications, generated file paths.
- Load chat history.

Frontend must not:
- Run AI inference.
- Run planner LLM.
- Validate plans.
- Call MCP servers directly.

### gRPC Server
- Exposes external app API.
- Receives frontend requests.
- Calls backend services.
- Does not contain heavy business logic.

### SessionManager
- Creates/loads session.
- Tracks current video.
- Tracks pending clarification.

### SQLite Storage
- Persists chat history.
- Stores video metadata.
- Caches transcript, visual analysis, graph/OCR results.
- Stores generated files.

### ContextBuilder
- Builds compact context for the planner.
- Includes current video status, recent messages, pending clarification, generated files.
- Does not dump everything blindly.

### PlannerService
- Uses one local LLM.
- Converts user query + context into JSON execution plan.
- Does not execute tools.

### PlanValidator
- Deterministic code.
- Validates schema, allowed agents/intents, dependencies, confidence, video availability.

### ClarificationManager
- Produces user-facing clarification question (elicitation) when plan is ambiguous/invalid.

### PlanExecutor
- Deterministic code.
- Executes validated JSON plan step by step.
- Calls appropriate agents.
- Passes previous step results into later steps.

### Agents
- Backend code modules.
- Handle task category.
- Call specific MCP servers through MCP Client Manager.

### MCP Client Manager
- Starts/connects to local MCP servers.
- Maintains MCP sessions.
- Provides agents with MCP clients.
- Handles connection/tool-call errors.
- Not the main orchestrator.

### MCP Servers
- Actual local MCP servers.
- Expose tools.
- Internally call services/models/libraries.

### OpenVINO
- Lives in model runtime layer.
- MVP: use OpenVINO for vision/object detection if possible.
