"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getAgentBehavior } from "@/lib/api-client";
import { useRefresh } from "@/lib/refresh-context";
import type { AgentBehavior as AgentBehaviorType } from "@vibe-coding-starter-kit/shared";

export function AgentBehaviorPanel() {
  const [data, setData] = useState<AgentBehaviorType | null>(null);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getAgentBehavior(7)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  if (loading) {
    return (
      <Card>
        <CardHeader><CardTitle>Agent Behavior (7d)</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}
        </CardContent>
      </Card>
    );
  }

  if (!data || data.total_queries === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>Agent Behavior (7d)</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground py-4 text-center">
            No agent data yet. Chat queries will populate this panel.
          </p>
        </CardContent>
      </Card>
    );
  }

  const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

  const metrics = [
    { label: "KB Retrieval Rate", value: pct(data.kb_only_rate) },
    { label: "Retry Loop Rate", value: pct(data.retry_loop_rate) },
    { label: "Avg Queries Generated", value: data.avg_queries_generated.toFixed(1) },
    { label: "Sufficient Evidence Rate", value: pct(data.sufficient_rate) },
  ];

  return (
    <Card>
      <CardHeader><CardTitle>Agent Behavior (7d)</CardTitle></CardHeader>
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
