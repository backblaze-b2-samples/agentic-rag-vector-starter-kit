"use client";

import { Check, FileText, Loader2 } from "lucide-react";
import type { PipelineStep } from "@vibe-coding-starter-kit/shared";

interface PipelineProgressProps {
  filename: string;
  steps: PipelineStep[];
}

/** Displays live RAG pipeline steps during document processing. */
export function PipelineProgress({ filename, steps }: PipelineProgressProps) {
  if (steps.length === 0) return null;

  return (
    <div className="rounded-lg border p-3 space-y-2">
      <div className="flex items-center gap-2 text-sm font-medium">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="truncate">Processing {filename}</span>
      </div>
      <div className="space-y-1 pl-6">
        {steps.map((step, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-muted-foreground">
            {step.status === "active" ? (
              <Loader2 className="h-3 w-3 animate-spin text-primary" />
            ) : (
              <Check className="h-3 w-3 text-green-500" />
            )}
            <span className={step.status === "active" ? "text-foreground" : ""}>
              {step.label}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
