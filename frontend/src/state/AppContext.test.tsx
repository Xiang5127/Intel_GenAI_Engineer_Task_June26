import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import * as desktop from "../lib/desktop";
import { AppProvider, useApp } from "./AppContext";
import { savePersistedState } from "./storage";

vi.mock("../lib/desktop", async () => {
  const actual = await vi.importActual<typeof import("../lib/desktop")>("../lib/desktop");
  return {
    ...actual,
    createSession: vi.fn(),
    getChatHistory: vi.fn(),
    sendMessage: vi.fn(),
  };
});

const wrapper = ({ children }: { children: ReactNode }) => <AppProvider>{children}</AppProvider>;

describe("AppProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.resetAllMocks();
  });

  it("resumes a persisted active session", async () => {
    savePersistedState({ sessionId: "session_saved", selectedVideo: null, generatedFiles: [] });
    vi.mocked(desktop.getChatHistory).mockResolvedValue({ messages: [] });

    const { result } = renderHook(() => useApp(), { wrapper });
    await waitFor(() => expect(result.current.initializing).toBe(false));

    expect(result.current.sessionId).toBe("session_saved");
    expect(result.current.backendStatus).toBe("connected");
  });

  it("creates a new session when the saved session is stale", async () => {
    savePersistedState({ sessionId: "session_stale", selectedVideo: null, generatedFiles: [] });
    vi.mocked(desktop.getChatHistory).mockRejectedValue({ code: "not_found", message: "missing" });
    vi.mocked(desktop.createSession).mockResolvedValue({
      session_id: "session_new",
      created_at: 1,
    });

    const { result } = renderHook(() => useApp(), { wrapper });
    await waitFor(() => expect(result.current.sessionId).toBe("session_new"));
    expect(result.current.backendStatus).toBe("connected");
  });

  it("keeps the UI recoverable when the backend is unavailable", async () => {
    vi.mocked(desktop.createSession).mockRejectedValue({
      code: "connection",
      message: "backend unavailable",
    });

    const { result } = renderHook(() => useApp(), { wrapper });
    await waitFor(() => expect(result.current.initializing).toBe(false));

    expect(result.current.backendStatus).toBe("unavailable");
    expect(result.current.error).toBe("backend unavailable");
    expect(result.current.initialize).toBeTypeOf("function");
  });

  it("optimistically sends and renders clarification", async () => {
    vi.mocked(desktop.createSession).mockResolvedValue({
      session_id: "session_new",
      created_at: 1,
    });
    vi.mocked(desktop.sendMessage).mockResolvedValue({
      assistant_message: "Do you want PDF or PowerPoint?",
      clarification_needed: true,
      clarification_question: "Do you want PDF or PowerPoint?",
      generated_files: [],
    });

    const { result } = renderHook(() => useApp(), { wrapper });
    await waitFor(() => expect(result.current.sessionId).toBe("session_new"));
    await act(() => result.current.sendMessage("Make a report"));

    expect(result.current.messages.map((message) => message.content)).toEqual([
      "Make a report",
      "Do you want PDF or PowerPoint?",
    ]);
    expect(result.current.clarificationQuestion).toBe("Do you want PDF or PowerPoint?");
  });
});
