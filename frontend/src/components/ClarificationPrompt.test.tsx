import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ClarificationPrompt } from "./ClarificationPrompt";

describe("ClarificationPrompt", () => {
  it("renders a planner clarification question", () => {
    render(<ClarificationPrompt question="PDF or PowerPoint?" />);
    expect(screen.getByText("PDF or PowerPoint?")).toBeInTheDocument();
  });

  it("renders nothing without a question", () => {
    const { container } = render(<ClarificationPrompt question="" />);
    expect(container).toBeEmptyDOMElement();
  });
});
