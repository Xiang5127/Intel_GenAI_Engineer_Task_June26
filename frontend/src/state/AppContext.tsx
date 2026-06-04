import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  createSession,
  getChatHistory,
  normalizeCommandError,
  openGeneratedFile,
  pickVideo,
  sendMessage as grpcSendMessage,
  uploadVideo,
} from "../lib/desktop";
import type {
  BackendStatus,
  ChatMessage,
  GeneratedFile,
  SelectedVideo,
} from "../types";
import {
  clearPersistedState,
  loadPersistedState,
  mergeGeneratedFiles,
  savePersistedState,
} from "./storage";

interface AppContextValue {
  sessionId: string | null;
  messages: ChatMessage[];
  generatedFiles: GeneratedFile[];
  selectedVideo: SelectedVideo | null;
  clarificationQuestion: string;
  backendStatus: BackendStatus;
  initializing: boolean;
  sending: boolean;
  uploading: boolean;
  error: string;
  initialize: () => Promise<void>;
  newSession: () => Promise<void>;
  selectVideo: () => Promise<void>;
  sendMessage: (message: string) => Promise<void>;
  openFile: (filePath: string) => Promise<void>;
  dismissError: () => void;
}

const AppContext = createContext<AppContextValue | null>(null);

function optimisticMessage(sessionId: string, role: "user" | "assistant", content: string): ChatMessage {
  return {
    message_id: `local_${crypto.randomUUID()}`,
    session_id: sessionId,
    role,
    content,
    created_at: Math.floor(Date.now() / 1000),
    pending: role === "user",
  };
}

export function AppProvider({ children }: { children: ReactNode }) {
  const initializationStarted = useRef(false);
  const persisted = useMemo(loadPersistedState, []);
  const [sessionId, setSessionId] = useState<string | null>(persisted.sessionId);
  const [selectedVideo, setSelectedVideo] = useState<SelectedVideo | null>(
    persisted.selectedVideo,
  );
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>(
    persisted.generatedFiles,
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [clarificationQuestion, setClarificationQuestion] = useState("");
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("connecting");
  const [initializing, setInitializing] = useState(true);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const setFailure = useCallback((value: unknown) => {
    const commandError = normalizeCommandError(value);
    setError(commandError.message);
    if (commandError.code === "unavailable" || commandError.code === "connection") {
      setBackendStatus("unavailable");
    }
    return commandError;
  }, []);

  const createFreshSession = useCallback(async () => {
    const created = await createSession("Local Video Analysis");
    setSessionId(created.session_id);
    setMessages([]);
    setSelectedVideo(null);
    setGeneratedFiles([]);
    setClarificationQuestion("");
    setBackendStatus("connected");
    setError("");
    return created.session_id;
  }, []);

  const initialize = useCallback(async () => {
    setInitializing(true);
    setBackendStatus("connecting");
    setError("");
    const stored = loadPersistedState();
    try {
      if (stored.sessionId) {
        const history = await getChatHistory(stored.sessionId);
        setSessionId(stored.sessionId);
        setMessages(history.messages);
        setSelectedVideo(stored.selectedVideo);
        setGeneratedFiles(stored.generatedFiles);
        setBackendStatus("connected");
      } else {
        await createFreshSession();
      }
    } catch (value) {
      const commandError = setFailure(value);
      if (commandError.code === "not_found") {
        clearPersistedState();
        try {
          await createFreshSession();
        } catch (retryError) {
          setFailure(retryError);
        }
      }
    } finally {
      setInitializing(false);
    }
  }, [createFreshSession, setFailure]);

  useEffect(() => {
    if (initializationStarted.current) return;
    initializationStarted.current = true;
    void initialize();
  }, [initialize]);

  useEffect(() => {
    savePersistedState({ sessionId, selectedVideo, generatedFiles });
  }, [sessionId, selectedVideo, generatedFiles]);

  const newSession = useCallback(async () => {
    setInitializing(true);
    try {
      await createFreshSession();
    } catch (value) {
      setFailure(value);
    } finally {
      setInitializing(false);
    }
  }, [createFreshSession, setFailure]);

  const selectVideo = useCallback(async () => {
    if (!sessionId) {
      setError("Connect to the backend before selecting a video.");
      return;
    }
    const path = await pickVideo();
    if (!path) return;
    setUploading(true);
    setError("");
    try {
      const uploaded = await uploadVideo(sessionId, path);
      setSelectedVideo(uploaded);
      setBackendStatus("connected");
    } catch (value) {
      setFailure(value);
    } finally {
      setUploading(false);
    }
  }, [sessionId, setFailure]);

  const refreshHistory = useCallback(async () => {
    if (!sessionId) return;
    const history = await getChatHistory(sessionId);
    setMessages(history.messages);
  }, [sessionId]);

  const sendMessage = useCallback(
    async (rawMessage: string) => {
      const message = rawMessage.trim();
      if (!message || !sessionId || sending) return;

      setSending(true);
      setError("");
      setClarificationQuestion("");
      const userMessage = optimisticMessage(sessionId, "user", message);
      setMessages((current) => [...current, userMessage]);

      try {
        const response = await grpcSendMessage(sessionId, message);
        const assistantMessage = optimisticMessage(
          sessionId,
          "assistant",
          response.assistant_message,
        );
        assistantMessage.pending = false;
        setMessages((current) => [
          ...current.map((item) =>
            item.message_id === userMessage.message_id ? { ...item, pending: false } : item,
          ),
          assistantMessage,
        ]);
        setClarificationQuestion(
          response.clarification_needed ? response.clarification_question : "",
        );
        setGeneratedFiles((current) =>
          mergeGeneratedFiles(current, response.generated_files),
        );
        setBackendStatus("connected");
      } catch (value) {
        setFailure(value);
        try {
          await refreshHistory();
        } catch {
          setMessages((current) =>
            current.filter((item) => item.message_id !== userMessage.message_id),
          );
        }
      } finally {
        setSending(false);
      }
    },
    [refreshHistory, sending, sessionId, setFailure],
  );

  const openFile = useCallback(
    async (filePath: string) => {
      try {
        await openGeneratedFile(filePath);
      } catch (value) {
        setFailure(value);
      }
    },
    [setFailure],
  );

  const value = useMemo<AppContextValue>(
    () => ({
      sessionId,
      messages,
      generatedFiles,
      selectedVideo,
      clarificationQuestion,
      backendStatus,
      initializing,
      sending,
      uploading,
      error,
      initialize,
      newSession,
      selectVideo,
      sendMessage,
      openFile,
      dismissError: () => setError(""),
    }),
    [
      backendStatus,
      clarificationQuestion,
      error,
      generatedFiles,
      initialize,
      initializing,
      messages,
      newSession,
      openFile,
      selectVideo,
      selectedVideo,
      sendMessage,
      sending,
      sessionId,
      uploading,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const value = useContext(AppContext);
  if (!value) throw new Error("useApp must be used inside AppProvider");
  return value;
}
