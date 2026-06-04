import type { GeneratedFile } from "../types";

function filename(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

export function GeneratedFilesPanel({
  files,
  onOpen,
}: {
  files: GeneratedFile[];
  onOpen: (path: string) => void;
}) {
  return (
    <section className="panel files-panel">
      <div className="panel-heading">
        <div>
          <p className="panel-kicker">OUTPUTS</p>
          <h2>Generated files</h2>
        </div>
        <span className="count-badge">{files.length}</span>
      </div>
      {files.length === 0 ? (
        <div className="empty-compact">PDF and PowerPoint outputs will appear here.</div>
      ) : (
        <div className="file-list">
          {files.map((file) => (
            <button
              className="generated-file"
              key={`${file.file_type}:${file.file_path}`}
              onClick={() => onOpen(file.file_path)}
              title={`Open ${file.file_path}`}
            >
              <span className={`file-type type-${file.file_type}`}>{file.file_type.toUpperCase()}</span>
              <span className="truncate">
                <strong>{filename(file.file_path)}</strong>
                <small>{new Date(file.created_at * 1000).toLocaleString()}</small>
              </span>
              <span className="open-symbol">Open</span>
            </button>
          ))}
        </div>
      )}
    </section>
  );
}
