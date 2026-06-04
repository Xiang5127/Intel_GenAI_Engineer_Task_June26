# Intel Local Video AI Desktop App

## Overview

This project is a local AI desktop application for analyzing short `.mp4` videos through a chat-style interface.

The app supports:
- Local video selection.
- Natural language interaction.
- Local speech transcription.
- Frame-based visual analysis.
- Object/graph/OCR detection where possible.
- PDF report generation.
- PowerPoint report generation.
- Persistent chat history.
- Local MCP server tool architecture.
- Local AI inference through Hugging Face/OpenVINO-compatible runtimes.

## Architecture

```txt
React + Tauri Frontend
  ↓ gRPC
Python Backend
  ├── SessionManager
  ├── SQLite Storage
  ├── ContextBuilder
  ├── PlannerService
  ├── PlanValidator
  ├── PlanExecutor
  ├── Agents
  └── MCP Client Manager
       ↓
Local MCP Servers
  ├── video_mcp_server
  ├── transcription_mcp_server
  ├── vision_mcp_server
  └── report_mcp_server
       ↓
Local Tools / Models / Libraries
```

## Setup

TODO

## Run Backend

TODO

## Run Frontend

TODO

## Example Queries

```txt
Transcribe the video.
Summarize the video.
What objects are shown in the video?
Are there any graphs in the video?
Create a PowerPoint with the key points.
Summarize our discussion so far and generate a PDF.
How many animals are in the video and export as PDF.
```

## What Works

TODO

## Known Limitations

- Vision analysis is frame-based, not full temporal reasoning.
- Graph detection is heuristic-based.
- Object counting is approximate.
- Local model size is constrained by available hardware.
- Planner output is validated by code, but planner quality depends on the local LLM.

## Future Improvements

- Use OpenVINO GenAI for planner/summarizer LLM.
- Improve OpenVINO vision model integration.
- Add official packaging.
- Add C# launcher.
- Add better chart understanding.
- Add vector search for large chat/video history.
