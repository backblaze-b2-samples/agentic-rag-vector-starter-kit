"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboardQueries } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import type { QueryLogEntry } from "@vibe-coding-starter-kit/shared";

export function RecentQueriesTable() {
  const [queries, setQueries] = useState<QueryLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getDashboardQueries(15)
      .then((d) => { if (!cancelled) setQueries(d); })
      .catch(() => { if (!cancelled) setQueries([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent Queries</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : queries.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No queries yet. Ask questions in Chat to see retrieval metrics here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Query</TableHead>
                  <TableHead>Route</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Evidence</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queries.map((q) => (
                  <TableRow key={q.id}>
                    <TableCell className="max-w-[250px] truncate font-medium">
                      {q.query}
                    </TableCell>
                    <TableCell>
                      <Badge variant={q.route === "kb_only" ? "default" : "secondary"} className="text-[10px]">
                        {q.route}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {q.top1_score !== null && q.top1_score !== undefined ? q.top1_score.toFixed(3) : "---"}
                    </TableCell>
                    <TableCell>{q.evidence_count}</TableCell>
                    <TableCell>{Math.round(q.latency_ms)}ms</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(q.ts)}
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
