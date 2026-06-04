import { ChatInput } from "./components/ChatInput";
import { ChatWindow } from "./components/ChatWindow";
import { ClarificationPrompt } from "./components/ClarificationPrompt";
import { GeneratedFilesPanel } from "./components/GeneratedFilesPanel";
import { Header } from "./components/Header";
import { VideoPicker } from "./components/VideoPicker";
import { useApp } from "./state/AppContext";

export default function App() {
  const app = useApp();
  const disconnected = app.backendStatus !== "connected" || !app.sessionId;

  return (
    <main className="app-shell">
      <Header
        status={app.backendStatus}
        sessionId={app.sessionId}
        busy={app.initializing || app.sending}
        onRetry={() => void app.initialize()}
        onNewSession={() => void app.newSession()}
      />

      {app.error && (
        <div className="error-banner" role="alert">
          <div>
            <strong>Something needs attention</strong>
            <span>{app.error}</span>
          </div>
          <button onClick={app.dismissError} aria-label="Dismiss error">Dismiss</button>
        </div>
      )}

      <div className="workspace">
        <aside className="sidebar">
          <VideoPicker
            video={app.selectedVideo}
            uploading={app.uploading}
            disabled={disconnected}
            onSelect={() => void app.selectVideo()}
          />
          <GeneratedFilesPanel files={app.generatedFiles} onOpen={(path) => void app.openFile(path)} />
        </aside>

        <section className="chat-panel">
          <div className="chat-topline">
            <div>
              <p className="panel-kicker">CONVERSATION</p>
              <h2>Analysis chat</h2>
            </div>
            {app.sessionId && <code title={app.sessionId}>{app.sessionId.slice(0, 20)}</code>}
          </div>
          <ClarificationPrompt question={app.clarificationQuestion} />
          <ChatWindow messages={app.messages} sending={app.sending} />
          <ChatInput disabled={disconnected || app.sending} onSend={app.sendMessage} />
        </section>
      </div>
    </main>
  );
}
