"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { streamChatMessage } from "@/lib/api-client";
import { useChat } from "@/lib/chat-context";
import { ChatInput } from "./chat-input";
import { MessageBubble } from "./message-bubble";
import { CitationPanel } from "./citation-panel";
import { PipelineSteps } from "./pipeline-steps";
import { SessionSidebar } from "./session-sidebar";
import type { Citation, PipelineStep, RetrievalInfo } from "@vibe-coding-starter-kit/shared";

export function ChatContainer() {
  const {
    messages, setMessages, sessionId, setSessionId, loadSessions,
  } = useChat();

  const [isStreaming, setIsStreaming] = useState(false);
  const [pipelineSteps, setPipelineSteps] = useState<PipelineStep[]>([]);
  const [showCitations, setShowCitations] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [panelCitations, setPanelCitations] = useState<Citation[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(async (text: string) => {
    setMessages((prev) => [
      ...prev,
      { role: "user", content: text, citations: [] },
      { role: "assistant", content: "", citations: [] },
    ]);
    setIsStreaming(true);
    setPipelineSteps([]);

    abortRef.current = new AbortController();
    let streamCitations: Citation[] = [];
    let retrievalData: RetrievalInfo | null = null;

    try {
      await streamChatMessage(
        { message: text, session_id: sessionId },
        (event) => {
          switch (event.type) {
            case "step":
              // Live pipeline step: update or append
              setPipelineSteps((prev) => {
                const label = event.label as string;
                const status = event.status as PipelineStep["status"];
                const existing = prev.findIndex((s) => s.label === label);
                if (existing >= 0) {
                  const updated = [...prev];
                  updated[existing] = { label, status };
                  return updated;
                }
                return [...prev, { label, status }];
              });
              break;

            case "metadata":
              if (event.session_id) setSessionId(event.session_id as string);
              else if (event.conversation_id) setSessionId(event.conversation_id as string);
              retrievalData = event.retrieval as RetrievalInfo;
              break;

            case "citations":
              streamCitations = event.citations as Citation[];
              break;

            case "token":
              // Clear pipeline steps once tokens start flowing
              setPipelineSteps([]);
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.role === "assistant") {
                  updated[updated.length - 1] = {
                    ...last,
                    content: last.content + (event.content as string),
                  };
                }
                return updated;
              });
              break;

            case "done":
              setPipelineSteps([]);
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.role === "assistant") {
                  updated[updated.length - 1] = {
                    ...last,
                    citations: streamCitations,
                    retrieval: retrievalData,
                  };
                }
                return updated;
              });
              if (streamCitations.length > 0) {
                setPanelCitations(streamCitations);
                setShowCitations(true);
              }
              break;
          }
        },
        abortRef.current.signal,
      );
      // Refresh session list (new session may have been created)
      loadSessions();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        toast.error("Failed to get response");
        setMessages((prev) => prev.filter((m) => m.content || m.role === "user"));
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [sessionId, setMessages, setSessionId, loadSessions]);

  function handleCitationClick(citation: Citation) {
    const msg = messages.find((m) =>
      m.citations.some((c) => c.index === citation.index && c.doc_id === citation.doc_id)
    );
    setPanelCitations(msg?.citations ?? [citation]);
    setActiveCitation(citation);
    setShowCitations(true);
  }

  return (
    <div className="flex h-full overflow-hidden">
      {/* Session sidebar */}
      <SessionSidebar />

      {/* Main chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        <ScrollArea className="flex-1 p-4" ref={scrollRef}>
          <div className="mx-auto max-w-3xl space-y-6">
            {messages.length === 0 && (
              <div className="flex flex-col items-center justify-center pt-20 text-center">
                <h2 className="text-2xl font-semibold mb-2">Ask your documents</h2>
                <p className="text-muted-foreground text-sm max-w-md">
                  Upload documents and ask questions. Responses are grounded in your
                  uploaded content with linked citations.
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i}>
                <MessageBubble
                  role={msg.role}
                  content={msg.content}
                  citations={msg.citations}
                  onCitationClick={handleCitationClick}
                />
                {msg.role === "assistant" && msg.retrieval && msg.retrieval.route !== "no_retrieval" && (
                  <div className="flex flex-wrap gap-2 ml-11 mt-1">
                    <Badge variant="outline" className="text-[10px]">
                      {msg.retrieval.evidence_used} sources
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      {msg.retrieval.queries_generated} queries
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      {msg.retrieval.retrieval_loops} loop{msg.retrieval.retrieval_loops !== 1 ? "s" : ""}
                    </Badge>
                    <Badge variant="outline" className="text-[10px]">
                      {Math.round(msg.retrieval.latency_ms)}ms
                    </Badge>
                  </div>
                )}
              </div>
            ))}

            {isStreaming && pipelineSteps.length > 0 && (
              <PipelineSteps steps={pipelineSteps} />
            )}
          </div>
        </ScrollArea>

        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>

      {/* Citation panel */}
      {showCitations && panelCitations.length > 0 && (
        <CitationPanel
          citations={panelCitations}
          activeCitation={activeCitation}
          onClose={() => {
            setShowCitations(false);
            setActiveCitation(null);
          }}
        />
      )}
    </div>
  );
}
