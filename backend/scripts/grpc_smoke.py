"""Phase 2 gRPC smoke test: start an in-process server and exercise all 4 RPCs.

    python -m backend.scripts.grpc_smoke

Spins up VideoAIService on a throwaway DB, then calls CreateSession ->
UploadVideo -> SendMessage -> GetChatHistory through a real gRPC channel.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import grpc

from backend.grpc_server import create_server

_GENERATED_DIR = Path(__file__).resolve().parents[1] / "generated"
if str(_GENERATED_DIR) not in sys.path:
    sys.path.insert(0, str(_GENERATED_DIR))

import video_ai_pb2 as pb2  # noqa: E402
import video_ai_pb2_grpc as pb2_grpc  # noqa: E402

ADDRESS = "127.0.0.1:50071"


def main() -> None:
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = str(Path(tmp) / "grpc_smoke.db")
        server = create_server(ADDRESS, db_path=db_path)
        server.start()
        print(f"[grpc] test server started on {ADDRESS}")
        try:
            with grpc.insecure_channel(ADDRESS) as channel:
                stub = pb2_grpc.VideoAIServiceStub(channel)

                created = stub.CreateSession(pb2.CreateSessionRequest(title="grpc smoke"))
                sid = created.session_id
                print(f"[CreateSession] -> {sid}")

                up = stub.UploadVideo(
                    pb2.UploadVideoRequest(session_id=sid, video_path="C:/tmp/sample.mp4")
                )
                print(f"[UploadVideo] -> {up.video_id} ({up.status})")

                resp = stub.SendMessage(
                    pb2.SendMessageRequest(session_id=sid, message="Transcribe the video.")
                )
                print(f"[SendMessage] -> {resp.assistant_message!r}")

                hist = stub.GetChatHistory(
                    pb2.GetChatHistoryRequest(session_id=sid, limit=0)
                )
                print(f"[GetChatHistory] -> {len(hist.messages)} message(s):")
                for m in hist.messages:
                    print(f"    {m.role}: {m.content}")

            assert len(hist.messages) == 2, "expected 1 user + 1 assistant message"
            print("[done] Phase 2 gRPC smoke test passed.")
        finally:
            server.stop(grace=None)


if __name__ == "__main__":
    main()
