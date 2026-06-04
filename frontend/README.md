# Frontend

React + Tauri desktop frontend for the Intel Local Video AI backend.

## Architecture

```text
React UI
  -> Tauri commands
  -> Rust tonic client
  -> Python VideoAIService at 127.0.0.1:50051
```

The frontend never calls MCP servers directly. The Python backend remains the
owner of planning, agents, MCP tools, storage, and local AI inference.

## Prerequisites

- Node.js 20 or newer.
- Rust stable.
- Windows: Microsoft C++ Build Tools and Edge WebView2.
- Python backend dependencies from `../backend/requirements.txt`.

System `protoc` is not required; the Rust build uses a vendored binary.

## Development

Start the backend manually from the repository root:

```powershell
$env:PLANNER_BACKEND = "heuristic"
python -m backend.main serve --address 127.0.0.1:50051
```

Then start the desktop frontend:

```powershell
cd frontend
npm install
npm run tauri dev
```

Use `VIDEO_AI_GRPC_ADDRESS` to override the backend endpoint. It must include the
scheme, for example `http://127.0.0.1:50051`.

## Verification

```powershell
npm test
npm run build
cargo test --manifest-path src-tauri/Cargo.toml
cargo check --manifest-path src-tauri/Cargo.toml
npm run tauri build
```

## Session and File History

The frontend resumes one active session using versioned browser local storage.
The current gRPC contract does not expose session listing or generated-file
history, so generated files returned by `SendMessage` are also cached locally.
Use **New session** to create a fresh backend session.

## Troubleshooting

- **Backend offline:** start `python -m backend.main serve`, then click the
  backend status button to retry.
- **Saved session missing:** the frontend automatically creates a replacement
  session when the backend reports `NOT_FOUND`.
- **Tauri fails to compile on Windows:** install Rust stable and the Microsoft
  C++ Build Tools workload.
