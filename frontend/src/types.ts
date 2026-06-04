export type BackendStatus = "connecting" | "connected" | "unavailable";
export type MessageRole = "user" | "assistant" | "system";

export interface ChatMessage {
  message_id: string;
  session_id: string;
  role: MessageRole;
  content: string;
  created_at: number;
  pending?: boolean;
}

export interface GeneratedFile {
  file_id: string;
  file_type: string;
  file_path: string;
  created_at: number;
}

export interface SelectedVideo {
  video_id: string;
  video_path: string;
  status: string;
}

export interface CreateSessionResponse {
  session_id: string;
  created_at: number;
}

export interface UploadVideoResponse extends SelectedVideo {}

export interface SendMessageResponse {
  assistant_message: string;
  clarification_needed: boolean;
  clarification_question: string;
  generated_files: GeneratedFile[];
}

export interface GetChatHistoryResponse {
  messages: ChatMessage[];
}

export interface CommandError {
  code: string;
  message: string;
}
