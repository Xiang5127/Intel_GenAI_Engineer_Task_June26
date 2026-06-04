# Intel Local Video AI Desktop App — Project Context

## Objective

Build an MVP local AI desktop application for short video analysis.

The application should allow a user to:
- Select a local `.mp4` video.
- Ask natural-language questions about the video.
- Transcribe the video.
- Analyze visual content from sampled frames.
- Detect objects / graph-like content / OCR text where possible.
- Generate PDF and PowerPoint reports.
- Persist chat history after restart.
- Run offline using local models.
- Use React + Tauri frontend.
- Use Python backend.
- Communicate through gRPC.
- Use actual local MCP servers for tools.
- Use OpenVINO or Hugging Face local models for inference.

## MVP Philosophy

This is not a perfect AI product.

This is a working engineering prototype that proves:
- Local desktop UI
- gRPC boundary
- Python backend orchestration
- JSON planning
- Deterministic validation/execution
- Local MCP tool servers
- Local model inference
- Persistent storage
- Report generation

Avoid over-engineering:
- No vector database for MVP
- No cloud APIs
- No LangChain/LangGraph initially
- No giant local models
- No perfect chart reasoning
- No beautiful UI before backend works
