"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { streamChatMessage } from "@/lib/api-client";
import { ChatInput } from "./chat-input";
import { MessageBubble } from "./message-bubble";
import { CitationPanel } from "./citation-panel";
import type { Citation, RetrievalInfo } from "@vibe-coding-starter-kit/shared";

interface Message {
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
}

export function ChatContainer() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [showCitations, setShowCitations] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  // Citations scoped to the message the user clicked on
  const [panelCitations, setPanelCitations] = useState<Citation[]>([]);
  const [retrievalInfo, setRetrievalInfo] = useState<RetrievalInfo | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(async (text: string) => {
    // Add user message
    const userMsg: Message = { role: "user", content: text, citations: [] };
    setMessages((prev) => [...prev, userMsg]);
    setIsStreaming(true);
    setRetrievalInfo(null);

    // Prepare assistant message placeholder
    const assistantMsg: Message = { role: "assistant", content: "", citations: [] };
    setMessages((prev) => [...prev, assistantMsg]);

    abortRef.current = new AbortController();
    let streamCitations: Citation[] = [];

    try {
      await streamChatMessage(
        { message: text, conversation_id: conversationId },
        (event) => {
          switch (event.type) {
            case "metadata":
              setConversationId(event.conversation_id as string);
              setRetrievalInfo(event.retrieval as RetrievalInfo);
              break;

            case "citations":
              streamCitations = event.citations as Citation[];
              break;

            case "token":
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.role === "assistant") {
                  last.content += event.content as string;
                }
                return updated;
              });
              break;

            case "done":
              // Attach citations to the final assistant message
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                if (last.role === "assistant") {
                  last.citations = streamCitations;
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
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        toast.error("Failed to get response");
        // Remove empty assistant message on error
        setMessages((prev) => prev.filter((m) => m.content || m.role === "user"));
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }, [conversationId]);

  function handleCitationClick(citation: Citation) {
    // Find the message containing this citation and show its full set
    const msg = messages.find((m) =>
      m.citations.some((c) => c.index === citation.index && c.doc_id === citation.doc_id)
    );
    setPanelCitations(msg?.citations ?? [citation]);
    setActiveCitation(citation);
    setShowCitations(true);
  }

  return (
    <div className="flex h-full">
      {/* Main chat area */}
      <div className="flex flex-1 flex-col min-w-0">
        {/* Messages */}
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
              <MessageBubble
                key={i}
                role={msg.role}
                content={msg.content}
                citations={msg.citations}
                onCitationClick={handleCitationClick}
              />
            ))}

            {/* Streaming indicator */}
            {isStreaming && messages[messages.length - 1]?.content === "" && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>Searching documents...</span>
              </div>
            )}

            {/* Retrieval metadata badge */}
            {retrievalInfo && retrievalInfo.route !== "no_retrieval" && (
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline" className="text-xs">
                  {retrievalInfo.evidence_used} sources used
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {retrievalInfo.queries_generated} queries
                </Badge>
                <Badge variant="outline" className="text-xs">
                  {Math.round(retrievalInfo.latency_ms)}ms
                </Badge>
              </div>
            )}
          </div>
        </ScrollArea>

        {/* Input */}
        <ChatInput onSend={handleSend} disabled={isStreaming} />
      </div>

      {/* Citation panel (conditional) */}
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
