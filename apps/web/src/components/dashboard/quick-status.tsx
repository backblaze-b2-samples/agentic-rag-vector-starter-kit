"use client";

import { useEffect, useState } from "react";
import { FileText, Layers, Search, Zap } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { getDashboardStats } from "@/lib/api-client";
import { useRefresh } from "@/lib/refresh-context";
import type { DashboardStats } from "@vibe-coding-starter-kit/shared";

export function QuickStatus() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getDashboardStats()
      .then((d) => { if (!cancelled) setStats(d); })
      .catch(() => {
        if (!cancelled) { setStats(null); toast.error("Failed to load dashboard stats"); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const cards = [
    {
      title: "Documents",
      value: stats?.total_documents ?? 0,
      sub: `${(stats?.total_chunks ?? 0).toLocaleString()} chunks indexed`,
      icon: FileText,
    },
    {
      title: "Total Queries",
      value: stats?.total_queries ?? 0,
      sub: `${stats?.queries_today ?? 0} today`,
      icon: Search,
    },
    {
      title: "Avg Relevance",
      value: stats?.avg_top1_score !== null && stats?.avg_top1_score !== undefined
        ? stats.avg_top1_score.toFixed(3) : "---",
      sub: `${stats?.pct_below_threshold ?? 0}% below threshold`,
      icon: Layers,
    },
    {
      title: "p95 Latency",
      value: stats ? `${stats.p95_latency_ms.toLocaleString()}ms` : "---",
      sub: `avg ${stats?.avg_latency_ms ?? 0}ms`,
      icon: Zap,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">{card.title}</CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <>
                <div className="text-2xl font-bold">{card.value}</div>
                {card.sub && (
                  <p className="text-xs text-muted-foreground">{card.sub}</p>
                )}
              </>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
