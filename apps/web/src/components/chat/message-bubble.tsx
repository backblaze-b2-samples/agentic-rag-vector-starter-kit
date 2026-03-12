"use client";

import { memo, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Bot, User } from "lucide-react";
import type { Citation, MessageRole } from "@vibe-coding-starter-kit/shared";

interface MessageBubbleProps {
  role: MessageRole;
  content: string;
  citations?: Citation[];
  onCitationClick?: (citation: Citation) => void;
}

/** Inject clickable citation buttons into markdown text nodes. */
function injectCitations(
  text: string,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
): ReactNode[] {
  if (!citations.length) return [text];
  const parts = text.split(/(\[\d+\])/g);
  return parts.map((part, i) => {
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
              transition-colors cursor-pointer mx-0.5 align-baseline"
            title={`${citation.doc_title} — ${citation.section_path}`}
          >
            {part}
          </button>
        );
      }
    }
    return <span key={i}>{part}</span>;
  });
}

/** Markdown renderer for assistant messages with citation support. */
const MarkdownContent = memo(function MarkdownContent({
  content,
  citations,
  onCitationClick,
}: {
  content: string;
  citations: Citation[];
  onCitationClick?: (citation: Citation) => void;
}) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Override text nodes to inject citation buttons
        p: ({ children }) => (
          <p className="mb-3 last:mb-0 leading-relaxed">
            {processChildren(children, citations, onCitationClick)}
          </p>
        ),
        strong: ({ children }) => (
          <strong className="font-semibold">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="italic">{children}</em>
        ),
        ul: ({ children }) => (
          <ul className="mb-3 last:mb-0 ml-4 space-y-1 list-disc marker:text-muted-foreground">
            {children}
          </ul>
        ),
        ol: ({ children }) => (
          <ol className="mb-3 last:mb-0 ml-4 space-y-1 list-decimal marker:text-muted-foreground">
            {children}
          </ol>
        ),
        li: ({ children }) => (
          <li className="leading-relaxed pl-1">{children}</li>
        ),
        h1: ({ children }) => (
          <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0">{children}</h3>
        ),
        h2: ({ children }) => (
          <h3 className="text-base font-semibold mb-2 mt-3 first:mt-0">{children}</h3>
        ),
        h3: ({ children }) => (
          <h4 className="text-sm font-semibold mb-1.5 mt-2 first:mt-0">{children}</h4>
        ),
        code: ({ children, className }) => {
          // Inline code vs code blocks
          const isBlock = className?.includes("language-");
          if (isBlock) {
            return (
              <code className="block bg-black/5 dark:bg-white/5 rounded-md p-3 my-2 text-[13px] font-mono overflow-x-auto">
                {children}
              </code>
            );
          }
          return (
            <code className="bg-black/5 dark:bg-white/5 rounded px-1.5 py-0.5 text-[13px] font-mono">
              {children}
            </code>
          );
        },
        pre: ({ children }) => (
          <pre className="mb-3 last:mb-0">{children}</pre>
        ),
        blockquote: ({ children }) => (
          <blockquote className="border-l-2 border-primary/30 pl-3 my-2 text-muted-foreground italic">
            {children}
          </blockquote>
        ),
        hr: () => <hr className="my-3 border-border" />,
        a: ({ href, children }) => (
          <a href={href} className="text-primary underline underline-offset-2 hover:text-primary/80" target="_blank" rel="noopener noreferrer">
            {children}
          </a>
        ),
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="w-full text-sm border-collapse">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-border px-2 py-1 text-left font-medium bg-muted/50">{children}</th>
        ),
        td: ({ children }) => (
          <td className="border border-border px-2 py-1">{children}</td>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
});

/** Recursively process React children to inject citations into text nodes. */
function processChildren(
  children: ReactNode,
  citations: Citation[],
  onCitationClick?: (citation: Citation) => void,
): ReactNode {
  if (typeof children === "string") {
    return injectCitations(children, citations, onCitationClick);
  }
  if (Array.isArray(children)) {
    return children.map((child, i) => {
      if (typeof child === "string") {
        return <span key={i}>{injectCitations(child, citations, onCitationClick)}</span>;
      }
      return child;
    });
  }
  return children;
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
        className={`max-w-[80%] rounded-2xl px-4 py-3
          ${isUser
            ? "bg-primary text-primary-foreground rounded-br-md"
            : "bg-muted rounded-bl-md"
          }`}
      >
        {isUser ? (
          <p className="text-[15px] leading-relaxed whitespace-pre-wrap">{content}</p>
        ) : (
          <div className="text-[15px] leading-relaxed">
            <MarkdownContent
              content={content}
              citations={citations}
              onCitationClick={onCitationClick}
            />
          </div>
        )}
      </div>
    </div>
  );
}
