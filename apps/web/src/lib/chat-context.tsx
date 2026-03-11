"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import {
  deleteChatSession,
  getChatSession,
  listChatSessions,
} from "@/lib/api-client";
import type { Citation, ChatSession, RetrievalInfo } from "@vibe-coding-starter-kit/shared";

export interface Message {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  retrieval?: RetrievalInfo | null;
}

interface ChatContextValue {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  sessionId: string | null;
  setSessionId: (id: string | null) => void;
  sessions: ChatSession[];
  loadSessions: () => Promise<void>;
  switchSession: (id: string) => Promise<void>;
  startNewChat: () => void;
  removeSession: (id: string) => Promise<void>;
}

const ChatContext = createContext<ChatContextValue>({
  messages: [],
  setMessages: () => {},
  sessionId: null,
  setSessionId: () => {},
  sessions: [],
  loadSessions: async () => {},
  switchSession: async () => {},
  startNewChat: () => {},
  removeSession: async () => {},
});

export function ChatProvider({ children }: { children: React.ReactNode }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  const loadSessions = useCallback(async () => {
    try {
      const list = await listChatSessions(50);
      setSessions(list);
    } catch {
      /* non-critical */
    }
  }, []);

  // Load sessions on mount
  useEffect(() => {
    let cancelled = false;
    listChatSessions(50)
      .then((list) => { if (!cancelled) setSessions(list); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const switchSession = useCallback(async (id: string) => {
    try {
      const data = await getChatSession(id);
      const msgs: Message[] = (data.messages as Array<{
        role: "user" | "assistant";
        content: string;
        citations?: Citation[];
        retrieval_metadata?: RetrievalInfo | null;
      }>).map((m) => ({
        role: m.role,
        content: m.content,
        citations: m.citations ?? [],
        retrieval: m.retrieval_metadata ?? null,
      }));
      setMessages(msgs);
      setSessionId(id);
    } catch {
      /* session may have been deleted */
    }
  }, []);

  const startNewChat = useCallback(() => {
    setMessages([]);
    setSessionId(null);
  }, []);

  const removeSession = useCallback(async (id: string) => {
    try {
      await deleteChatSession(id);
      setSessions((prev) => prev.filter((s) => s.session_id !== id));
      if (sessionId === id) {
        setMessages([]);
        setSessionId(null);
      }
    } catch {
      /* ignore */
    }
  }, [sessionId]);

  return (
    <ChatContext.Provider
      value={{
        messages, setMessages, sessionId, setSessionId,
        sessions, loadSessions, switchSession, startNewChat, removeSession,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  return useContext(ChatContext);
}
