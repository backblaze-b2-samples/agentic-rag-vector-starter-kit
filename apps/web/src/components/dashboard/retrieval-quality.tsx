"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getRetrievalQuality } from "@/lib/api-client";
import { useRefresh } from "@/lib/refresh-context";
import type { RetrievalQuality as RetrievalQualityType } from "@vibe-coding-starter-kit/shared";

export function RetrievalQualityPanel() {
  const [data, setData] = useState<RetrievalQualityType | null>(null);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getRetrievalQuality(7)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle>Retrieval Quality (7d)</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  if (!data || data.total_evaluated === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>Retrieval Quality (7d)</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-4 text-center">
            No retrieval data yet. Ask questions in Chat to generate metrics.
          </p>
        </CardContent>
      </Card>
    );
  }

  const metrics = [
    { label: "Avg Top-1 Score", value: data.avg_top1_score?.toFixed(3) ?? "---" },
    { label: "Below 0.3 Threshold", value: `${data.pct_below_threshold}%` },
    { label: "Avg Evidence Count", value: data.avg_evidence_count.toFixed(1) },
    { label: "Total Evaluated", value: data.total_evaluated },
  ];

  return (
    <Card>
      <CardHeader><CardTitle>Retrieval Quality (7d)</CardTitle></CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-4">
          {metrics.map((m) => (
            <div key={m.label}>
              <dt className="text-xs text-muted-foreground">{m.label}</dt>
              <dd className="text-lg font-semibold">{m.value}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
