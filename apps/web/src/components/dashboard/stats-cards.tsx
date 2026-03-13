"use client";

import { useEffect, useState } from "react";
import { FileIcon, HardDrive, Upload, Download } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";
import { getFileStats } from "@/lib/api-client";
import { useRefresh } from "@/lib/refresh-context";
import type { UploadStats } from "@vibe-coding-starter-kit/shared";

export function StatsCards() {
  const [stats, setStats] = useState<UploadStats | null>(null);
  const [loadedKey, setLoadedKey] = useState<number | null>(null);
  const { refreshKey } = useRefresh();

  const loading = loadedKey !== refreshKey;

  useEffect(() => {
    let cancelled = false;
    getFileStats()
      .then((data) => { if (!cancelled) setStats(data); })
      .catch(() => {
        if (!cancelled) {
          setStats(null);
          toast.error("Failed to load stats");
        }
      })
      .finally(() => { if (!cancelled) setLoadedKey(refreshKey); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const cards = [
    {
      title: "Total Files",
      value: stats?.total_files ?? 0,
      icon: FileIcon,
    },
    {
      title: "Storage Used",
      value: stats?.total_size_human ?? "0 B",
      icon: HardDrive,
    },
    {
      title: "Uploads Today",
      value: stats?.uploads_today ?? 0,
      icon: Upload,
    },
    {
      title: "Total Downloads",
      value: stats?.total_downloads ?? 0,
      icon: Download,
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {cards.map((card) => (
        <Card key={card.title}>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">
              {card.title}
            </CardTitle>
            <card.icon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-7 w-20" />
            ) : (
              <div className="text-2xl font-bold">{card.value}</div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
