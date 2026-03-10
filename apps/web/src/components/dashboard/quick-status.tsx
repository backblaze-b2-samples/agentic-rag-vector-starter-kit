"use client";

import { useEffect, useState } from "react";
import { Search, Clock, FileText, Layers, Zap, Calendar } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { getDashboardStats } from "@/lib/api-client";
import { useRefresh } from "@/lib/refresh-context";
import { formatDate } from "@/lib/utils";
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
      title: "Queries Today",
      value: stats?.queries_today ?? 0,
      sub: `${stats?.queries_7d ?? 0} last 7 days`,
      icon: Search,
    },
    {
      title: "p95 Latency",
      value: stats ? `${stats.p95_latency_ms.toLocaleString()}ms` : "---",
      sub: `avg ${stats?.avg_latency_ms ?? 0}ms`,
      icon: Zap,
    },
    {
      title: "Documents",
      value: stats?.total_documents ?? 0,
      sub: `${(stats?.total_chunks ?? 0).toLocaleString()} chunks`,
      icon: FileText,
    },
    {
      title: "Avg Top-1 Score",
      value: stats?.avg_top1_score !== null && stats?.avg_top1_score !== undefined ? stats.avg_top1_score.toFixed(3) : "---",
      sub: `${stats?.pct_below_threshold ?? 0}% below 0.3`,
      icon: Layers,
    },
    {
      title: "KB Queries",
      value: stats?.kb_only_count ?? 0,
      sub: `${stats?.no_retrieval_count ?? 0} no-retrieval`,
      icon: Clock,
    },
    {
      title: "Last Ingestion",
      value: stats?.last_ingestion_ts ? formatDate(stats.last_ingestion_ts) : "Never",
      sub: "",
      icon: Calendar,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
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
