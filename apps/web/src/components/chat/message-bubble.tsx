"use client";

import { Bot, User } from "lucide-react";
import type { Citation, MessageRole } from "@vibe-coding-starter-kit/shared";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

/** Render message content with clickable [N] citation links. */
function renderContent(
  content: string,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
) {
  if (!citations.length) return <p className="whitespace-pre-wrap">{content}</p>;

  // Split on citation markers like [1], [2], etc.
  const parts = content.split(/(\[\d+\])/g);
  return (
    <p className="whitespace-pre-wrap">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const idx = parseInt(match[1], 10);
          const citation = citations.find((c) => c.index === idx);
          if (citation) {
            return (
              <button
                key={i}
                onClick={() => onCitationClick?.(citation)}
                className="inline-flex items-center justify-center rounded bg-primary/10
                  px-1.5 py-0.5 text-xs font-medium text-primary hover:bg-primary/20
                  transition-colors cursor-pointer mx-0.5"
                title={`${citation.doc_title} — ${citation.section_path}`}
              >
                {part}
              </button>
            );
          }
        }
        return <span key={i}>{part}</span>;
      })}
    </p>
  );
}

export function MessageBubble({ role, content, citations = [], onCitationClick }: MessageBubbleProps) {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full
          ${isUser ? "bg-primary text-primary-foreground" : "bg-muted"}`}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Message */}
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed
          ${isUser
            ? "bg-primary text-primary-foreground rounded-br-md"
            : "bg-muted rounded-bl-md"
          }`}
      >
        {renderContent(content, citations, onCitationClick)}
      </div>
    </div>
  );
}
