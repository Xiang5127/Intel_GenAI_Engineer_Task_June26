import type { ChatMessage } from "../types";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const time = new Date(message.created_at * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
  return (
    <article className={`message message-${message.role} ${message.pending ? "message-pending" : ""}`}>
      <div className="message-meta">
        <span>{message.role === "assistant" ? "Video AI" : message.role}</span>
        <time>{time}</time>
      </div>
      <p>{message.content}</p>
    </article>
  );
}
