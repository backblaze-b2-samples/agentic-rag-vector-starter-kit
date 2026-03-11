"use client";

import { Check, Loader2 } from "lucide-react";
import type { PipelineStep } from "@vibe-coding-starter-kit/shared";

interface PipelineStepsProps {
  steps: PipelineStep[];
}

/** Displays live retrieval pipeline steps during streaming. */
export function PipelineSteps({ steps }: PipelineStepsProps) {
  if (steps.length === 0) return null;

  return (
    <div className="ml-11 space-y-1 py-2">
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
  );
}
