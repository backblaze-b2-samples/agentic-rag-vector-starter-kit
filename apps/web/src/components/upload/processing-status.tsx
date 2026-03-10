"use client";

import { CheckCircle2, AlertCircle, XCircle, FileText, Layers, Hash } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { PipelineResult } from "@vibe-coding-starter-kit/shared";

interface ProcessingStatusProps {
  filename: string;
  contentType: string;
  pipeline: PipelineResult | null;
}

const PROCESSABLE_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/csv",
  "text/markdown",
  "application/json",
]);

export function ProcessingStatus({ filename, contentType, pipeline }: ProcessingStatusProps) {
  // Non-text files skip RAG processing
  if (!PROCESSABLE_TYPES.has(contentType)) {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <AlertCircle className="h-3 w-3" />
        <span>{filename}: not a text document — skipped RAG processing</span>
      </div>
    );
  }

  // Pipeline failed
  if (pipeline?.status === "failed") {
    return (
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs text-destructive">
          <XCircle className="h-3 w-3" />
          <span>{filename} — pipeline failed</span>
        </div>
        {pipeline.error_message && (
          <p className="text-xs text-muted-foreground pl-5">{pipeline.error_message}</p>
        )}
      </div>
    );
  }

  // Pipeline completed — show details
  if (pipeline?.status === "completed" && pipeline.chunk_count > 0) {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CheckCircle2 className="h-3 w-3 text-green-600" />
          <span>{filename} processed</span>
          <Badge variant="outline" className="text-[10px]">
            <FileText className="h-2.5 w-2.5 mr-1" />
            Searchable
          </Badge>
        </div>
        <div className="flex flex-wrap gap-3 pl-5 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Layers className="h-3 w-3" />
            {pipeline.chunk_count} chunks
          </span>
          <span className="flex items-center gap-1">
            <Hash className="h-3 w-3" />
            {pipeline.total_tokens.toLocaleString()} tokens
          </span>
          <Badge variant="secondary" className="text-[10px]">
            {pipeline.classification}
          </Badge>
        </div>
        {pipeline.summary && (
          <p className="text-xs text-muted-foreground pl-5 line-clamp-2">
            {pipeline.summary}
          </p>
        )}
      </div>
    );
  }

  // Fallback: completed but no chunks (non-processable content type handled by pipeline)
  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <CheckCircle2 className="h-3 w-3 text-green-600" />
      <span>{filename} uploaded</span>
    </div>
  );
}
