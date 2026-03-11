"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Layers, Hash } from "lucide-react";
import { getDashboardIngestions } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import type { IngestionLogEntry } from "@vibe-coding-starter-kit/shared";

export function KnowledgeBase() {
  const [docs, setDocs] = useState<IngestionLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getDashboardIngestions(50)
      .then((d) => {
        if (cancelled) return;
        // Show only the latest ingestion per filename (re-uploads replace)
        const latest = new Map<string, IngestionLogEntry>();
        for (const doc of d) {
          if (!latest.has(doc.filename)) latest.set(doc.filename, doc);
        }
        setDocs(Array.from(latest.values()));
      })
      .catch(() => { if (!cancelled) setDocs([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle>Knowledge Base</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="space-y-2">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-full" />
            </div>
          ))}
        </CardContent>
      </Card>
    );
  }

  const successDocs = docs.filter((d) => d.status === "completed" && d.chunk_count > 0);
  const failedDocs = docs.filter((d) => d.status === "failed");

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Knowledge Base</CardTitle>
        <span className="text-sm text-muted-foreground">
          {successDocs.length} document{successDocs.length !== 1 ? "s" : ""} indexed
        </span>
      </CardHeader>
      <CardContent>
        {successDocs.length === 0 && failedDocs.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No documents in the knowledge base yet. Upload documents to get started.
          </p>
        ) : (
          <div className="space-y-4">
            {successDocs.map((doc) => (
              <div key={doc.id} className="border rounded-lg p-4 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                    <span className="font-medium truncate">{doc.filename}</span>
                  </div>
                  <Badge variant="secondary" className="text-[10px] shrink-0">
                    {doc.classification}
                  </Badge>
                </div>
                {doc.summary && (
                  <p className="text-sm text-muted-foreground line-clamp-3">
                    {doc.summary}
                  </p>
                )}
                <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Layers className="h-3 w-3" />
                    {doc.chunk_count} chunks
                  </span>
                  <span className="flex items-center gap-1">
                    <Hash className="h-3 w-3" />
                    {doc.total_tokens.toLocaleString()} tokens
                  </span>
                  <span>Indexed {formatDate(doc.ts)}</span>
                </div>
              </div>
            ))}
            {failedDocs.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-destructive">
                  Failed ({failedDocs.length})
                </h4>
                {failedDocs.map((doc) => (
                  <div key={doc.id} className="border border-destructive/30 rounded-lg p-3 text-sm">
                    <span className="font-medium">{doc.filename}</span>
                    {doc.error_message && (
                      <p className="text-xs text-muted-foreground mt-1">{doc.error_message}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
