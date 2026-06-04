export function ClarificationPrompt({ question }: { question: string }) {
  if (!question) return null;
  return (
    <aside className="clarification" role="status">
      <span>Clarification needed</span>
      <p>{question}</p>
    </aside>
  );
}
