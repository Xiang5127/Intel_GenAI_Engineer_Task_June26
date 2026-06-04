import type { BackendStatus } from "../types";

interface HeaderProps {
  status: BackendStatus;
  sessionId: string | null;
  busy: boolean;
  onRetry: () => void;
  onNewSession: () => void;
}

export function Header({ status, sessionId, busy, onRetry, onNewSession }: HeaderProps) {
  return (
    <header className="app-header">
      <div>
        <p className="eyebrow">LOCAL DESKTOP INTELLIGENCE</p>
        <h1>Video AI Workbench</h1>
      </div>
      <div className="header-actions">
        <button
          className={`status-pill status-${status}`}
          type="button"
          onClick={status === "unavailable" ? onRetry : undefined}
          title={status === "unavailable" ? "Retry backend connection" : sessionId ?? ""}
        >
          <span className="status-dot" />
          {status === "connected"
            ? "Backend connected"
            : status === "connecting"
              ? "Connecting"
              : "Backend offline - retry"}
        </button>
        <button className="button button-secondary" disabled={busy} onClick={onNewSession}>
          New session
        </button>
      </div>
    </header>
  );
}
