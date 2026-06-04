# Windsurf Master Prompt

You are coding an MVP for an Intel interview assignment.

Build a local AI desktop application for short video analysis.

## Hard Requirements

- Frontend: React + Tauri desktop app.
- Backend: Python.
- Communication: gRPC using `.proto` contract.
- User can select local `.mp4` file.
- User can chat with the app.
- Persistent chat history after restart.
- Backend uses a Planner LLM that outputs JSON execution plans.
- Plans are validated by deterministic code.
- Valid plans are executed by deterministic PlanExecutor.
- Executor calls local agents.
- Agents call actual local MCP servers.
- MCP servers expose tools for video processing, transcription, vision analysis, and report generation.
- All AI inference must run locally using Hugging Face or OpenVINO-compatible models.
- No cloud APIs.
- No public MCP servers.
- Generate PDF and PPTX outputs.

## MVP Constraints

Do not over-engineer.
Do not use LangChain/LangGraph initially.
Do not use vector DB.
Do not implement real-time streaming.
Do not focus on beautiful UI before backend works.
Do not use large models.

## Architecture

Frontend:
- React + Tauri
- Video picker
- Chat UI
- Generated files panel
- gRPC client

Backend:
- Python gRPC server
- SessionManager
- SQLite storage
- ContextBuilder
- PlannerService
- PlanValidator
- ClarificationManager
- PlanExecutor
- Agent registry
- MCP Client Manager
- Agents:
  - TranscriptionAgent
  - VisionAgent
  - SummaryAgent
  - ReportAgent
- Actual MCP servers:
  - video_mcp_server
  - transcription_mcp_server
  - vision_mcp_server
  - report_mcp_server

OpenVINO:
- Reserve runtime layer.
- Prefer using OpenVINO for vision/object detection in MVP.
- If OpenVINO integration blocks progress, implement a fallback vision runtime and keep OpenVINO runtime abstraction.

## Development Method

Implement in phases.

Do not generate the full system all at once.
After each phase, ensure the project runs and simple tests pass.

Start with backend skeleton and SQLite storage.
Then video processing MCP server.
Then transcription.
Then vision.
Then reports.
Then planner/executor.
Then frontend.

## Coding Standards

- Keep modules small.
- Use type hints.
- Use Pydantic for plan schema validation.
- Use clear error handling.
- Avoid hidden global state.
- Use local paths only.
- Store outputs under backend/outputs.
- Add README instructions as implementation progresses.

## Current Task

Implement the requested phase only.
Do not jump ahead.
At the end of each phase, summarize:
- files created/modified
- how to run/test
- what works
- what remains
