fn main() {
    let protoc = protoc_bin_vendored::protoc_bin_path().expect("vendored protoc unavailable");
    std::env::set_var("PROTOC", protoc);

    tonic_build::configure()
        .build_server(false)
        .compile_protos(
            &["../../backend/proto/video_ai.proto"],
            &["../../backend/proto"],
        )
        .expect("failed to compile video_ai.proto");

    tauri_build::build();
}
