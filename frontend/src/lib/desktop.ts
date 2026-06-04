import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

import type {
  CommandError,
  CreateSessionResponse,
  GetChatHistoryResponse,
  SendMessageResponse,
  UploadVideoResponse,
} from "../types";

export async function createSession(title?: string): Promise<CreateSessionResponse> {
  return invoke<CreateSessionResponse>("grpc_create_session", { title });
}

export async function uploadVideo(
  sessionId: string,
  videoPath: string,
): Promise<UploadVideoResponse> {
  return invoke<UploadVideoResponse>("grpc_upload_video", { sessionId, videoPath });
}

export async function sendMessage(
  sessionId: string,
  message: string,
): Promise<SendMessageResponse> {
  return invoke<SendMessageResponse>("grpc_send_message", { sessionId, message });
}

export async function getChatHistory(
  sessionId: string,
  limit = 0,
): Promise<GetChatHistoryResponse> {
  return invoke<GetChatHistoryResponse>("grpc_get_chat_history", { sessionId, limit });
}

export async function openGeneratedFile(filePath: string): Promise<void> {
  return invoke<void>("open_generated_file", { filePath });
}

export async function pickVideo(): Promise<string | null> {
  const result = await open({
    multiple: false,
    directory: false,
    filters: [{ name: "MP4 video", extensions: ["mp4"] }],
  });
  return typeof result === "string" ? result : null;
}

export function normalizeCommandError(error: unknown): CommandError {
  if (typeof error === "object" && error !== null) {
    const candidate = error as Partial<CommandError>;
    if (typeof candidate.message === "string") {
      return {
        code: typeof candidate.code === "string" ? candidate.code : "unknown",
        message: candidate.message,
      };
    }
  }
  return {
    code: "unknown",
    message: error instanceof Error ? error.message : String(error),
  };
}
