import { beforeEach, describe, expect, it } from "vitest";

import type { GeneratedFile } from "../types";
import { loadPersistedState, mergeGeneratedFiles, savePersistedState } from "./storage";

describe("frontend persistence", () => {
  beforeEach(() => localStorage.clear());

  it("round-trips the active session state", () => {
    savePersistedState({
      sessionId: "session_1",
      selectedVideo: { video_id: "video_1", video_path: "C:/demo.mp4", status: "stored" },
      generatedFiles: [],
    });
    expect(loadPersistedState().sessionId).toBe("session_1");
    expect(loadPersistedState().selectedVideo?.video_id).toBe("video_1");
  });

  it("deduplicates generated files by type and path", () => {
    const first: GeneratedFile = {
      file_id: "file_1",
      file_type: "pdf",
      file_path: "C:/report.pdf",
      created_at: 1,
    };
    const replacement = { ...first, file_id: "file_2", created_at: 2 };
    expect(mergeGeneratedFiles([first], [replacement])).toEqual([replacement]);
  });
});
