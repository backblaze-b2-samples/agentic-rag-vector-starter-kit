"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Bot, User } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboardSessionMessages } from "@/lib/api-client";
import type { SessionMessageDetail } from "@vibe-coding-starter-kit/shared";

interface SessionDetailProps {
  sessionId: string;
  onBack: () => void;
}

function ScoreBadge({ label, value }: { label: string; value: number | null }) {
  if (value === null || value === undefined) return null;
  const color =
    value >= 0.7 ? "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200"
    : value >= 0.4 ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
    : "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium ${color}`}>
      {label}: {value.toFixed(2)}
    </span>
  );
}

export function SessionDetail({ sessionId, onBack }: SessionDetailProps) {
  const [messages, setMessages] = useState<SessionMessageDetail[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    getDashboardSessionMessages(sessionId)
      .then((d) => { if (!cancelled) setMessages(d); })
      .catch(() => { if (!cancelled) setMessages([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center gap-3">
        <Button variant="ghost" size="icon" onClick={onBack} className="shrink-0">
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <CardTitle className="truncate">Session Messages</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-16 w-full" />)}
          </div>
        ) : messages.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No messages found for this session.
          </p>
        ) : (
          <div className="space-y-3">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`rounded-lg border p-3 ${
                  msg.role === "user" ? "bg-muted/30" : "bg-background"
                }`}
              >
                {/* Header: role icon + metadata badges */}
                <div className="flex items-start justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    {msg.role === "user" ? (
                      <User className="h-4 w-4 text-muted-foreground shrink-0" />
                    ) : (
                      <Bot className="h-4 w-4 text-primary shrink-0" />
                    )}
                    <span className="text-xs font-medium capitalize">{msg.role}</span>
                    {msg.route && (
                      <Badge variant="outline" className="text-[10px]">{msg.route}</Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {msg.latency_ms !== null && (
                      <Badge variant="secondary" className="text-[10px]">
                        {Math.round(msg.latency_ms)}ms
                      </Badge>
                    )}
                    {msg.evidence_count !== null && msg.evidence_count > 0 && (
                      <Badge variant="secondary" className="text-[10px]">
                        {msg.evidence_count} sources
                      </Badge>
                    )}
                  </div>
                </div>

                {/* Message content (truncated for long messages) */}
                <p className="text-sm line-clamp-4 whitespace-pre-wrap">{msg.content}</p>

                {/* RAGAS scores for assistant messages */}
                {msg.role === "assistant" && (msg.faithfulness !== null || msg.context_precision !== null) && (
                  <div className="flex flex-wrap gap-2 mt-2 pt-2 border-t">
                    <ScoreBadge label="Faithfulness" value={msg.faithfulness} />
                    <ScoreBadge label="Context Precision" value={msg.context_precision} />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
