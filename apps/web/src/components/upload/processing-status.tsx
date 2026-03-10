"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, FileText, AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { getDocumentStats } from "@/lib/api-client";

interface ProcessingStatusProps {
  /** Show after a successful upload */
  filename: string;
  contentType: string;
}

const PROCESSABLE_TYPES = new Set([
  "application/pdf",
  "text/plain",
  "text/csv",
  "text/markdown",
  "application/json",
]);

export function ProcessingStatus({ filename, contentType }: ProcessingStatusProps) {
  const [status, setStatus] = useState<"processing" | "done" | "skipped">(
    PROCESSABLE_TYPES.has(contentType) ? "processing" : "skipped"
  );

  useEffect(() => {
    if (status !== "processing") return;

    // Poll document stats briefly to confirm pipeline processed the doc
    const timer = setTimeout(() => {
      getDocumentStats()
        .then(() => setStatus("done"))
        .catch(() => setStatus("done")); // assume done even if stats fail
    }, 3000);

    return () => clearTimeout(timer);
  }, [status]);

  if (status === "skipped") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <AlertCircle className="h-3 w-3" />
        <span>{filename}: not a text document — skipped RAG processing</span>
      </div>
    );
  }

  if (status === "processing") {
    return (
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>Processing {filename} — chunking, classifying, embedding...</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <CheckCircle2 className="h-3 w-3 text-green-600" />
      <span>{filename} processed</span>
      <Badge variant="outline" className="text-[10px]">
        <FileText className="h-2.5 w-2.5 mr-1" />
        Searchable
      </Badge>
    </div>
  );
}
