"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboardIngestions } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import type { IngestionLogEntry } from "@vibe-coding-starter-kit/shared";

export function IngestionPanel() {
  const [ingestions, setIngestions] = useState<IngestionLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getDashboardIngestions(15)
      .then((d) => { if (!cancelled) setIngestions(d); })
      .catch(() => { if (!cancelled) setIngestions([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  const failedCount = ingestions.filter((i) => i.status === "failed").length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Recent Ingestions</CardTitle>
        {failedCount > 0 && (
          <Badge variant="destructive" className="text-[10px]">
            {failedCount} failed
          </Badge>
        )}
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : ingestions.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No ingestions yet. Upload documents to see pipeline results here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Filename</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Chunks</TableHead>
                  <TableHead>Tokens</TableHead>
                  <TableHead>Classification</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {ingestions.map((ing) => (
                  <TableRow key={ing.id}>
                    <TableCell className="max-w-[200px] truncate font-medium">
                      {ing.filename}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={ing.status === "completed" ? "default" : "destructive"}
                        className="text-[10px]"
                      >
                        {ing.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{ing.chunk_count}</TableCell>
                    <TableCell>{ing.total_tokens.toLocaleString()}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-[10px]">
                        {ing.classification}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(ing.ts)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
