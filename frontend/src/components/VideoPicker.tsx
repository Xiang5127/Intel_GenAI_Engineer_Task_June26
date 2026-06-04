import type { SelectedVideo } from "../types";

interface VideoPickerProps {
  video: SelectedVideo | null;
  uploading: boolean;
  disabled: boolean;
  onSelect: () => void;
}

function filename(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

export function VideoPicker({ video, uploading, disabled, onSelect }: VideoPickerProps) {
  return (
    <section className="panel video-picker">
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">SOURCE</p>
          <h2>Selected video</h2>
        </div>
        <button className="button button-primary" disabled={disabled || uploading} onClick={onSelect}>
          {uploading ? "Uploading..." : video ? "Change video" : "Choose MP4"}
        </button>
      </div>
      {video ? (
        <div className="video-card">
          <div className="file-mark">MP4</div>
          <div className="truncate">
            <strong>{filename(video.video_path)}</strong>
            <span title={video.video_path}>{video.video_path}</span>
          </div>
          <span className="tag">{video.status}</span>
        </div>
      ) : (
        <div className="empty-compact">
          Choose a local MP4 before asking questions about video content.
        </div>
      )}
    </section>
  );
}
