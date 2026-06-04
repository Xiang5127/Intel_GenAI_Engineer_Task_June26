# Acceptance Checklist

## Core Requirements

- [ ] React + Tauri frontend exists.
- [ ] Python backend exists.
- [ ] gRPC contract exists.
- [ ] Frontend can send message to backend.
- [ ] User can select local `.mp4`.
- [ ] Backend stores selected video.
- [ ] Chat UI exists.
- [ ] Chat history persists after restart.
- [ ] SQLite storage exists.
- [ ] ContextBuilder exists.
- [ ] PlannerService outputs JSON plan.
- [ ] PlanValidator validates plans using code.
- [ ] PlanExecutor executes validated plans.
- [ ] TranscriptionAgent exists.
- [ ] VisionAgent exists.
- [ ] SummaryAgent exists.
- [ ] ReportAgent exists.
- [ ] Actual local MCP servers exist.
- [ ] video_mcp_server exposes tools.
- [ ] transcription_mcp_server exposes tools.
- [ ] vision_mcp_server exposes tools.
- [ ] report_mcp_server exposes tools.
- [ ] Local transcription works.
- [ ] Frame extraction works.
- [ ] Basic vision analysis works.
- [ ] PDF generation works.
- [ ] PPTX generation works.
- [ ] No cloud APIs are used.
- [ ] At least one component uses or is ready for OpenVINO local inference.
- [ ] README exists.
- [ ] Sample queries documented.
- [ ] Sample outputs included.
- [ ] Limitations documented.

## Demo Queries

- [ ] "Transcribe the video."
- [ ] "Summarize the video."
- [ ] "What objects are shown in the video?"
- [ ] "Are there any graphs in the video?"
- [ ] "Create a PowerPoint with the key points."
- [ ] "Summarize our discussion so far and generate a PDF."
- [ ] "How many animals are in the video and export as PDF."
- [ ] "Make a report." → should ask clarification.

## Non-goals

- [ ] No real-time video streaming.
- [ ] No cloud AI API.
- [ ] No public MCP server dependency.
- [ ] No vector database.
- [ ] No complex LangChain/LangGraph dependency.
