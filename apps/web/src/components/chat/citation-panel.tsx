"use client";

import { ExternalLink, FileText, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Citation } from "@vibe-coding-starter-kit/shared";

interface CitationPanelProps {
  citations: Citation[];
  activeCitation?: Citation | null;
  onClose: () => void;
}

export function CitationPanel({ citations, activeCitation, onClose }: CitationPanelProps) {
  if (!citations.length) return null;

  return (
    <div className="w-72 min-w-0 border-l bg-background flex flex-col h-full overflow-hidden shrink-0">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Sources ({citations.length})</h3>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </div>

      {/* Citation list */}
      <ScrollArea className="flex-1">
        <div className="space-y-3 p-4">
          {citations.map((citation) => (
            <div
              key={citation.index}
              className={`rounded-lg border p-3 text-sm transition-colors
                ${activeCitation?.index === citation.index
                  ? "border-primary bg-primary/5"
                  : "hover:bg-muted/50"
                }`}
            >
              {/* Citation header */}
              <div className="flex items-start gap-2 mb-2 min-w-0">
                <Badge variant="outline" className="shrink-0 text-[10px]">
                  [{citation.index}]
                </Badge>
                <div className="min-w-0 overflow-hidden">
                  <p className="font-medium text-xs truncate">{citation.doc_title}</p>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {citation.section_path}
                  </p>
                </div>
              </div>

              {/* Page info */}
              {citation.page && (
                <p className="text-xs text-muted-foreground mb-2">
                  Page {citation.page}
                </p>
              )}

              {/* Excerpt */}
              <p className="text-xs text-muted-foreground line-clamp-4 mb-2">
                {citation.chunk_text}
              </p>

              {/* Download link */}
              {citation.download_url && (
                <a
                  href={citation.download_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] text-primary hover:underline"
                >
                  <FileText className="h-3 w-3 shrink-0" />
                  <span className="truncate">View source</span>
                  <ExternalLink className="h-2.5 w-2.5 shrink-0" />
                </a>
              )}
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
