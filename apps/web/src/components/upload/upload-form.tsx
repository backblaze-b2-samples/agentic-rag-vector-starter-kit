"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import type { FileRejection } from "react-dropzone";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Dropzone } from "./dropzone";
import { UploadProgress, type UploadItem } from "./upload-progress";
import { ProcessingStatus } from "./processing-status";
import { PipelineProgress } from "./pipeline-progress";
import { uploadFileStreaming } from "@/lib/api-client";
import { humanizeBytes } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import type { PipelineResult, PipelineStep } from "@vibe-coding-starter-kit/shared";

interface CompletedFile {
  filename: string;
  contentType: string;
  pipeline: PipelineResult | null;
}

interface ActivePipeline {
  filename: string;
  steps: PipelineStep[];
}

export function UploadForm() {
  const [items, setItems] = useState<UploadItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [completedFiles, setCompletedFiles] = useState<CompletedFile[]>([]);
  const [activePipelines, setActivePipelines] = useState<ActivePipeline[]>([]);
  const { triggerRefresh } = useRefresh();

  const handleFilesRejected = useCallback((rejections: FileRejection[]) => {
    for (const rejection of rejections) {
      const name = rejection.file.name;
      const errors = rejection.errors.map((e) => {
        if (e.code === "file-too-large") {
          return `exceeds 100MB limit (${humanizeBytes(rejection.file.size)})`;
        }
        return e.message;
      });
      toast.error(`${name}: ${errors.join(", ")}`);
    }
  }, []);

  const handleFilesSelected = useCallback((files: File[]) => {
    const newItems: UploadItem[] = files.map((file) => ({
      id: `${file.name}-${Date.now()}-${Math.random()}`,
      file,
      progress: 0,
      status: "uploading" as const,
    }));
    setItems((prev) => [...prev, ...newItems]);
    setUploading(true);

    const uploadQueue = async () => {
      let anySuccess = false;
      for (const item of newItems) {
        // Add active pipeline tracker for this file
        const pipelineKey = item.file.name;
        setActivePipelines((prev) => [...prev, { filename: pipelineKey, steps: [] }]);

        try {
          // Mark upload progress to 50% (uploading phase)
          setItems((prev) =>
            prev.map((i) => i.id === item.id ? { ...i, progress: 50 } : i)
          );

          let pipelineResult: PipelineResult | null = null;

          await uploadFileStreaming(item.file, (event) => {
            switch (event.type) {
              case "uploaded":
                // File is in B2, pipeline starting
                setItems((prev) =>
                  prev.map((i) => i.id === item.id ? { ...i, progress: 100 } : i)
                );
                break;

              case "step":
                // Pipeline step update
                setActivePipelines((prev) =>
                  prev.map((p) => {
                    if (p.filename !== pipelineKey) return p;
                    const label = event.label as string;
                    const status = event.status as PipelineStep["status"];
                    const existing = p.steps.findIndex((s) => s.label === label);
                    if (existing >= 0) {
                      const updated = [...p.steps];
                      updated[existing] = { label, status };
                      return { ...p, steps: updated };
                    }
                    return { ...p, steps: [...p.steps, { label, status }] };
                  })
                );
                break;

              case "done":
                pipelineResult = (event.pipeline as PipelineResult) ?? null;
                break;
            }
          });

          // Mark complete
          setItems((prev) =>
            prev.map((i) => i.id === item.id ? { ...i, status: "complete", progress: 100 } : i)
          );
          // Remove active pipeline, add to completed
          setActivePipelines((prev) => prev.filter((p) => p.filename !== pipelineKey));
          setCompletedFiles((prev) => [...prev, {
            filename: item.file.name,
            contentType: item.file.type || "application/octet-stream",
            pipeline: pipelineResult,
          }]);
          toast.success(`${item.file.name} processed successfully`);
          anySuccess = true;
        } catch (err) {
          const message = err instanceof Error ? err.message : "Upload failed";
          setItems((prev) =>
            prev.map((i) => i.id === item.id ? { ...i, status: "error", error: message } : i)
          );
          setActivePipelines((prev) => prev.filter((p) => p.filename !== pipelineKey));
          toast.error(`Failed to upload ${item.file.name}: ${message}`);
        }
      }
      setUploading(false);
      if (anySuccess) triggerRefresh();
    };

    uploadQueue().catch(console.error);
  }, [triggerRefresh]);

  const clearCompleted = useCallback(() => {
    setItems((prev) => prev.filter((i) => i.status === "uploading"));
    setCompletedFiles([]);
    setActivePipelines([]);
  }, []);

  const hasCompleted = items.some(
    (i) => i.status === "complete" || i.status === "error"
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload Files</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <Dropzone
          onFilesSelected={handleFilesSelected}
          onFilesRejected={handleFilesRejected}
          disabled={uploading}
        />
        <UploadProgress items={items} />
        {/* Live pipeline steps for files being processed */}
        {activePipelines.map((p) => (
          <PipelineProgress key={p.filename} filename={p.filename} steps={p.steps} />
        ))}
        {/* Completed pipeline results */}
        {completedFiles.length > 0 && (
          <div className="space-y-1">
            {completedFiles.map((f, i) => (
              <ProcessingStatus key={i} filename={f.filename} contentType={f.contentType} pipeline={f.pipeline} />
            ))}
          </div>
        )}
        {hasCompleted && !uploading && (
          <div className="flex justify-end">
            <Button variant="outline" size="sm" onClick={clearCompleted}>
              Clear completed
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
