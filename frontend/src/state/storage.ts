import type { GeneratedFile, SelectedVideo } from "../types";

const STORAGE_KEY = "intel-video-ai.frontend-state";
const STORAGE_VERSION = 1;

export interface PersistedState {
  version: number;
  sessionId: string | null;
  selectedVideo: SelectedVideo | null;
  generatedFiles: GeneratedFile[];
}

const EMPTY_STATE: PersistedState = {
  version: STORAGE_VERSION,
  sessionId: null,
  selectedVideo: null,
  generatedFiles: [],
};

export function loadPersistedState(): PersistedState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return EMPTY_STATE;
    const parsed = JSON.parse(raw) as Partial<PersistedState>;
    if (parsed.version !== STORAGE_VERSION) return EMPTY_STATE;
    return {
      version: STORAGE_VERSION,
      sessionId: typeof parsed.sessionId === "string" ? parsed.sessionId : null,
      selectedVideo: parsed.selectedVideo ?? null,
      generatedFiles: Array.isArray(parsed.generatedFiles) ? parsed.generatedFiles : [],
    };
  } catch {
    return EMPTY_STATE;
  }
}

export function savePersistedState(state: Omit<PersistedState, "version">): void {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ version: STORAGE_VERSION, ...state }),
  );
}

export function clearPersistedState(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function mergeGeneratedFiles(
  existing: GeneratedFile[],
  incoming: GeneratedFile[],
): GeneratedFile[] {
  const byPath = new Map<string, GeneratedFile>();
  for (const file of [...existing, ...incoming]) {
    byPath.set(`${file.file_type}:${file.file_path}`, file);
  }
  return [...byPath.values()].sort((a, b) => b.created_at - a.created_at);
}
