import { useEffect, useRef } from "react";

import type { ChatMessage } from "../types";
import { MessageBubble } from "./MessageBubble";

export function ChatWindow({ messages, sending }: { messages: ChatMessage[]; sending: boolean }) {
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, sending]);

  return (
    <div className="chat-window" aria-live="polite">
      {messages.length === 0 ? (
        <div className="empty-chat">
          <span className="empty-orbit">AI</span>
          <h2>Ready when your backend is.</h2>
          <p>Select a video, then ask for a transcript, visual analysis, summary, PDF, or PowerPoint.</p>
        </div>
      ) : (
        messages.map((message) => <MessageBubble key={message.message_id} message={message} />)
      )}
      {sending && <div className="typing-indicator"><span /><span /><span /></div>}
      <div ref={bottomRef} />
    </div>
  );
}
