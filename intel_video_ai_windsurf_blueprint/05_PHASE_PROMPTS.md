# Phase-by-Phase Windsurf Prompts

Use these prompts one at a time. Do not paste all at once.

---

## Phase 0 Prompt — Project Skeleton

Create the repository skeleton for the Intel Local Video AI MVP.

Requirements:
- Create `/frontend` placeholder for React + Tauri.
- Create `/backend` Python structure.
- Create `/backend/proto/video_ai.proto`.
- Create `/backend/storage/schema.sql`.
- Create `/backend/outputs/audio`, `/backend/outputs/frames`, `/backend/outputs/reports`, `/backend/outputs/analysis_json`.
- Create root README.md with project overview and setup TODO.
- Create backend requirements.txt placeholder.

Do not implement AI models yet.
Do not implement frontend UI yet.
Do not install unnecessary frameworks.

Expected output:
- Clean folder structure.
- Initial proto contract with CreateSession, UploadVideo, SendMessage, GetChatHistory.
- SQLite schema for sessions, chat_messages, videos, video_analysis, generated_files.

---

## Phase 1 Prompt — Backend Storage + Session

Implement backend storage and session management.

Create:
- backend/storage/db.py
- backend/session/session_manager.py
- backend/context/context_builder.py
- backend/main.py for simple CLI smoke test

Implement:
- initialize SQLite database from schema.sql
- create_session()
- get_session()
- save_chat_message()
- get_recent_messages()
- save_video()
- set_current_video()
- get_current_video()
- basic context builder returning session_id, current_video, recent_messages, pending_clarification

Add a CLI smoke test:
- initialize DB
- create session
- save a dummy message
- print context

Do not implement gRPC yet.
Do not implement MCP yet.

---

## Phase 2 Prompt — gRPC Server Skeleton

Implement Python gRPC server for the existing proto.

Create:
- backend/grpc_server.py
- generated proto files if needed
- update backend/main.py to start gRPC server

Implement methods:
- CreateSession
- UploadVideo
- SendMessage with dummy response
- GetChatHistory

SendMessage should:
- save user message
- save dummy assistant response
- return dummy assistant response

Do not implement planner/agents yet.

---

## Phase 3 Prompt — Actual Video MCP Server

Implement actual local MCP server for video processing.

Create:
- backend/mcp_servers/video_mcp_server.py
- backend/services/video_processing.py
- backend/mcp_clients/mcp_client_manager.py minimal client connection if possible

MCP tools:
- get_video_metadata(video_path)
- extract_audio(video_path)
- extract_frames(video_path, interval_seconds=5)

Use local libraries only.
Prefer ffmpeg if available, otherwise OpenCV/moviepy.

Outputs:
- audio under backend/outputs/audio
- frames under backend/outputs/frames/{video_id}/

Add a backend CLI test that calls the MCP server/tool on a sample MP4 path.

Do not implement transcription yet.

---

## Phase 4 Prompt — Transcription MCP + Agent

Implement transcription.

Create:
- backend/mcp_servers/transcription_mcp_server.py
- backend/services/speech_to_text.py
- backend/runtimes/whisper_runtime.py
- backend/agents/base_agent.py
- backend/agents/transcription_agent.py

MCP tool:
- transcribe_audio(audio_path) -> transcript

Agent:
- TranscriptionAgent.handle(intent, inputs, context)
- Should call video MCP extract_audio if needed
- Should call transcription MCP transcribe_audio
- Should save transcript into video_analysis table

Use local model only:
- Prefer whisper tiny/base or faster-whisper.
- Must not call cloud APIs.

Add test path:
- Given a video path, extract audio, transcribe, save transcript.

---

## Phase 5 Prompt — Vision MCP + Agent

Implement vision analysis.

Create:
- backend/mcp_servers/vision_mcp_server.py
- backend/services/vision_analysis.py
- backend/services/graph_detection.py
- backend/runtimes/openvino_vision_runtime.py
- backend/agents/vision_agent.py

MCP tools:
- detect_objects(frame_paths)
- count_objects(frame_paths, target)
- run_ocr(frame_paths)
- detect_graphs(frame_paths)

MVP implementation:
- Use OpenVINO vision runtime if feasible.
- If model setup is blocking, implement a fallback runtime and preserve OpenVINOVisionRuntime abstraction.
- Graph detection can be heuristic-based using OCR keywords/line-shape hints.

Agent:
- Extract frames through video MCP.
- Analyze frames through vision MCP.
- Save objects_json, ocr_json, graph_json, visual_summary.

---

## Phase 6 Prompt — Report MCP + Summary/Report Agents

Implement report generation.

Create:
- backend/mcp_servers/report_mcp_server.py
- backend/services/report_generator.py
- backend/services/summarization.py
- backend/agents/summary_agent.py
- backend/agents/report_agent.py

MCP tools:
- generate_pdf_report(report_data)
- generate_pptx_report(slide_data)

Use:
- ReportLab or fpdf2 for PDF.
- python-pptx for PPTX.

SummaryAgent:
- Can use simple rule-based summary first.
- Later can reuse local planner LLM with a different prompt.
- Should produce structured report_data and slide_data.

ReportAgent:
- Accepts previous step result or stored analysis.
- Generates PDF/PPTX.
- Saves generated file record.

---

## Phase 7 Prompt — Planner, Validator, Executor

Implement JSON planning architecture.

Create:
- backend/planner/plan_schema.py
- backend/planner/planner_prompt.py
- backend/planner/planner_service.py
- backend/planner/plan_validator.py
- backend/planner/clarification_manager.py
- backend/planner/plan_executor.py

PlannerService:
- For now, allow a simple local model adapter/stub.
- Must expose generate_plan(user_query, context) -> raw JSON plan.
- Include prompt that lists allowed agents/intents and asks for JSON only.

PlanValidator:
- Use Pydantic.
- Validate schema.
- Validate confidence.
- Validate dependencies.
- Validate video-required intents.
- Validate clarification.

PlanExecutor:
- Execute steps in order.
- Resolve source_step dependencies.
- Call agents through registry.
- Return final response.

Update gRPC SendMessage:
- save user message
- build context
- generate plan
- validate
- clarify if invalid/low confidence
- execute if valid
- save assistant response
- return response

Test:
- "Transcribe the video"
- "What objects are shown?"
- "How many animals are in the video and export as PDF"
- "Make a report" should ask clarification

---

## Phase 8 Prompt — React + Tauri Frontend

Implement frontend.

Create:
- Tauri + React app if not already initialized.
- Components:
  - VideoPicker
  - ChatWindow
  - ChatInput
  - MessageBubble
  - GeneratedFilesPanel
  - ClarificationPrompt

Connect to backend through gRPC client.

Features:
- Create/load session.
- Select MP4 and call UploadVideo.
- Send user message.
- Display assistant response.
- Show clarification.
- Show generated file path.
- Load chat history.

Keep UI simple and usable.
Do not over-style.

---

## Phase 9 Prompt — Documentation + Sample Outputs

Prepare submission.

Create/update:
- README.md
- docs/architecture.md
- docs/limitations.md
- docs/demo_script.md
- sample_inputs/README.md
- sample_outputs/README.md

README must include:
- What the app does
- Architecture
- Setup steps
- How to run backend
- How to run frontend
- Example queries
- What works
- Known limitations
- Future improvements

Generate at least:
- sample transcript
- sample PDF
- sample PPTX
