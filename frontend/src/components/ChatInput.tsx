import { type FormEvent, useState } from "react";

export function ChatInput({
  disabled,
  onSend,
}: {
  disabled: boolean;
  onSend: (message: string) => Promise<void>;
}) {
  const [message, setMessage] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const trimmed = message.trim();
    if (!trimmed || disabled) return;
    setMessage("");
    await onSend(trimmed);
  }

  return (
    <form className="chat-input" onSubmit={submit}>
      <textarea
        aria-label="Message"
        value={message}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            event.currentTarget.form?.requestSubmit();
          }
        }}
        placeholder="Ask about the video or request a report..."
        rows={2}
        disabled={disabled}
      />
      <button className="button button-primary send-button" disabled={disabled || !message.trim()}>
        Send
      </button>
    </form>
  );
}
