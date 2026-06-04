use std::{
    env,
    path::{Path, PathBuf},
    process::Command,
};

use serde::Serialize;
use tauri::State;
use tokio::sync::Mutex;
use tonic::{
    transport::{Channel, Endpoint},
    Request, Status,
};

pub mod video_ai {
    tonic::include_proto!("video_ai");
}

use video_ai::{
    video_ai_service_client::VideoAiServiceClient, ChatMessage, CreateSessionRequest,
    GeneratedFile, GetChatHistoryRequest, SendMessageRequest, UploadVideoRequest,
};

const DEFAULT_GRPC_ADDRESS: &str = "http://127.0.0.1:50051";

pub struct GrpcState {
    endpoint: String,
    channel: Mutex<Option<Channel>>,
}

impl GrpcState {
    pub fn from_environment() -> Self {
        let endpoint =
            env::var("VIDEO_AI_GRPC_ADDRESS").unwrap_or_else(|_| DEFAULT_GRPC_ADDRESS.to_string());
        Self {
            endpoint,
            channel: Mutex::new(None),
        }
    }

    async fn client(&self) -> Result<VideoAiServiceClient<Channel>, CommandError> {
        let mut shared = self.channel.lock().await;
        if shared.is_none() {
            let endpoint = Endpoint::from_shared(self.endpoint.clone())
                .map_err(|error| CommandError::new("invalid_endpoint", error.to_string()))?;
            *shared = Some(endpoint.connect().await?);
        }
        Ok(VideoAiServiceClient::new(
            shared.as_ref().expect("channel initialized").clone(),
        ))
    }
}

#[derive(Debug, Serialize)]
pub struct CommandError {
    code: String,
    message: String,
}

impl CommandError {
    fn new(code: impl Into<String>, message: impl Into<String>) -> Self {
        Self {
            code: code.into(),
            message: message.into(),
        }
    }
}

impl From<Status> for CommandError {
    fn from(status: Status) -> Self {
        Self::new(grpc_code(status.code()), status.message())
    }
}

impl From<tonic::transport::Error> for CommandError {
    fn from(error: tonic::transport::Error) -> Self {
        Self::new("connection", error.to_string())
    }
}

fn grpc_code(code: tonic::Code) -> &'static str {
    match code {
        tonic::Code::Ok => "ok",
        tonic::Code::Cancelled => "cancelled",
        tonic::Code::Unknown => "unknown",
        tonic::Code::InvalidArgument => "invalid_argument",
        tonic::Code::DeadlineExceeded => "deadline_exceeded",
        tonic::Code::NotFound => "not_found",
        tonic::Code::AlreadyExists => "already_exists",
        tonic::Code::PermissionDenied => "permission_denied",
        tonic::Code::ResourceExhausted => "resource_exhausted",
        tonic::Code::FailedPrecondition => "failed_precondition",
        tonic::Code::Aborted => "aborted",
        tonic::Code::OutOfRange => "out_of_range",
        tonic::Code::Unimplemented => "unimplemented",
        tonic::Code::Internal => "internal",
        tonic::Code::Unavailable => "unavailable",
        tonic::Code::DataLoss => "data_loss",
        tonic::Code::Unauthenticated => "unauthenticated",
    }
}

#[derive(Serialize)]
pub struct CreateSessionResponseDto {
    session_id: String,
    created_at: i64,
}

#[derive(Serialize)]
pub struct UploadVideoResponseDto {
    video_id: String,
    video_path: String,
    status: String,
}

#[derive(Serialize)]
pub struct GeneratedFileDto {
    file_id: String,
    file_type: String,
    file_path: String,
    created_at: i64,
}

impl From<GeneratedFile> for GeneratedFileDto {
    fn from(file: GeneratedFile) -> Self {
        Self {
            file_id: file.file_id,
            file_type: file.file_type,
            file_path: file.file_path,
            created_at: file.created_at,
        }
    }
}

#[derive(Serialize)]
pub struct SendMessageResponseDto {
    assistant_message: String,
    clarification_needed: bool,
    clarification_question: String,
    generated_files: Vec<GeneratedFileDto>,
}

#[derive(Serialize)]
pub struct ChatMessageDto {
    message_id: String,
    session_id: String,
    role: String,
    content: String,
    created_at: i64,
}

impl From<ChatMessage> for ChatMessageDto {
    fn from(message: ChatMessage) -> Self {
        Self {
            message_id: message.message_id,
            session_id: message.session_id,
            role: message.role,
            content: message.content,
            created_at: message.created_at,
        }
    }
}

#[derive(Serialize)]
pub struct GetChatHistoryResponseDto {
    messages: Vec<ChatMessageDto>,
}

#[tauri::command(rename_all = "camelCase")]
pub async fn grpc_create_session(
    state: State<'_, GrpcState>,
    title: Option<String>,
) -> Result<CreateSessionResponseDto, CommandError> {
    let response = state
        .client()
        .await?
        .create_session(Request::new(CreateSessionRequest {
            title: title.unwrap_or_default(),
        }))
        .await?
        .into_inner();
    Ok(CreateSessionResponseDto {
        session_id: response.session_id,
        created_at: response.created_at,
    })
}

#[tauri::command(rename_all = "camelCase")]
pub async fn grpc_upload_video(
    state: State<'_, GrpcState>,
    session_id: String,
    video_path: String,
) -> Result<UploadVideoResponseDto, CommandError> {
    validate_mp4_path(Path::new(&video_path))?;
    let response = state
        .client()
        .await?
        .upload_video(Request::new(UploadVideoRequest {
            session_id,
            video_path,
        }))
        .await?
        .into_inner();
    Ok(UploadVideoResponseDto {
        video_id: response.video_id,
        video_path: response.video_path,
        status: response.status,
    })
}

#[tauri::command(rename_all = "camelCase")]
pub async fn grpc_send_message(
    state: State<'_, GrpcState>,
    session_id: String,
    message: String,
) -> Result<SendMessageResponseDto, CommandError> {
    if message.trim().is_empty() {
        return Err(CommandError::new(
            "invalid_argument",
            "Message cannot be empty.",
        ));
    }
    let response = state
        .client()
        .await?
        .send_message(Request::new(SendMessageRequest {
            session_id,
            message,
        }))
        .await?
        .into_inner();
    Ok(SendMessageResponseDto {
        assistant_message: response.assistant_message,
        clarification_needed: response.clarification_needed,
        clarification_question: response.clarification_question,
        generated_files: response
            .generated_files
            .into_iter()
            .map(Into::into)
            .collect(),
    })
}

#[tauri::command(rename_all = "camelCase")]
pub async fn grpc_get_chat_history(
    state: State<'_, GrpcState>,
    session_id: String,
    limit: Option<i32>,
) -> Result<GetChatHistoryResponseDto, CommandError> {
    let response = state
        .client()
        .await?
        .get_chat_history(Request::new(GetChatHistoryRequest {
            session_id,
            limit: limit.unwrap_or(0),
        }))
        .await?
        .into_inner();
    Ok(GetChatHistoryResponseDto {
        messages: response.messages.into_iter().map(Into::into).collect(),
    })
}

#[tauri::command(rename_all = "camelCase")]
pub async fn open_generated_file(file_path: String) -> Result<(), CommandError> {
    let path = validate_generated_file(Path::new(&file_path))?;
    open_with_default_application(&path)
}

fn validate_mp4_path(path: &Path) -> Result<(), CommandError> {
    if !path.is_absolute() {
        return Err(CommandError::new(
            "invalid_path",
            "Video path must be absolute.",
        ));
    }
    if !path.is_file() {
        return Err(CommandError::new(
            "not_found",
            "Selected video file does not exist.",
        ));
    }
    if !has_extension(path, &["mp4"]) {
        return Err(CommandError::new(
            "invalid_file_type",
            "Only MP4 videos are supported.",
        ));
    }
    Ok(())
}

fn validate_generated_file(path: &Path) -> Result<PathBuf, CommandError> {
    if !path.is_absolute() {
        return Err(CommandError::new(
            "invalid_path",
            "Generated file path must be absolute.",
        ));
    }
    if !path.is_file() {
        return Err(CommandError::new(
            "not_found",
            "Generated file does not exist.",
        ));
    }
    if !has_extension(path, &["pdf", "pptx"]) {
        return Err(CommandError::new(
            "invalid_file_type",
            "Only generated PDF and PPTX files can be opened.",
        ));
    }
    path.canonicalize()
        .map_err(|error| CommandError::new("invalid_path", error.to_string()))
}

fn has_extension(path: &Path, allowed: &[&str]) -> bool {
    path.extension()
        .and_then(|value| value.to_str())
        .map(|value| {
            allowed
                .iter()
                .any(|allowed| value.eq_ignore_ascii_case(allowed))
        })
        .unwrap_or(false)
}

fn open_with_default_application(path: &Path) -> Result<(), CommandError> {
    #[cfg(target_os = "windows")]
    let mut command = {
        let mut command = Command::new("cmd");
        command.arg("/C").arg("start").arg("").arg(path);
        command
    };

    #[cfg(target_os = "macos")]
    let mut command = {
        let mut command = Command::new("open");
        command.arg(path);
        command
    };

    #[cfg(all(unix, not(target_os = "macos")))]
    let mut command = {
        let mut command = Command::new("xdg-open");
        command.arg(path);
        command
    };

    command
        .spawn()
        .map(|_| ())
        .map_err(|error| CommandError::new("open_failed", error.to_string()))
}

#[cfg(test)]
mod tests {
    use std::fs;

    use super::*;

    #[test]
    fn accepts_supported_generated_extensions_case_insensitively() {
        assert!(has_extension(Path::new("report.PDF"), &["pdf", "pptx"]));
        assert!(has_extension(Path::new("slides.pptx"), &["pdf", "pptx"]));
        assert!(!has_extension(Path::new("notes.txt"), &["pdf", "pptx"]));
    }

    #[test]
    fn maps_grpc_status_to_structured_error() {
        let error = CommandError::from(Status::not_found("session missing"));
        assert_eq!(error.code, "not_found");
        assert_eq!(error.message, "session missing");
    }

    #[test]
    fn rejects_an_existing_non_mp4_video() {
        let path = env::temp_dir().join("video-ai-invalid-video.txt");
        fs::write(&path, "not a video").expect("temporary test file");
        let error = validate_mp4_path(&path).expect_err("non-MP4 path should fail");
        fs::remove_file(path).expect("remove temporary test file");
        assert_eq!(error.code, "invalid_file_type");
    }
}
