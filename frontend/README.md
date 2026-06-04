# Frontend (React + Tauri) — Placeholder

This directory will hold the React + Tauri desktop frontend, implemented in **Phase 8**.

Planned components:
- `VideoPicker` — select a local `.mp4`.
- `ChatWindow` / `MessageBubble` — conversation display.
- `ChatInput` — send messages.
- `GeneratedFilesPanel` — list generated PDF/PPTX files.
- `ClarificationPrompt` — show planner clarification questions.

Connectivity:
- Talks to the Python backend via the gRPC contract in `../backend/proto/video_ai.proto`
  (transport for the Tauri webview — likely gRPC-web or a Tauri-side proxy — decided in Phase 8).

Toolchain note: requires Node.js (installed) and the Rust + Tauri toolchain (to be installed before Phase 8).

> Do not implement UI before the backend works (see blueprint MVP philosophy).
