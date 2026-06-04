mod grpc_bridge;

use grpc_bridge::{
    grpc_create_session, grpc_get_chat_history, grpc_send_message, grpc_upload_video,
    open_generated_file, GrpcState,
};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(GrpcState::from_environment())
        .invoke_handler(tauri::generate_handler![
            grpc_create_session,
            grpc_upload_video,
            grpc_send_message,
            grpc_get_chat_history,
            open_generated_file
        ])
        .run(tauri::generate_context!())
        .expect("error while running Intel Local Video AI");
}
