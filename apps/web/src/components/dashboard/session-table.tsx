"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { getDashboardSessions } from "@/lib/api-client";
import { formatDate } from "@/lib/utils";
import { useRefresh } from "@/lib/refresh-context";
import type { SessionSummary } from "@vibe-coding-starter-kit/shared";

interface SessionTableProps {
  onSelectSession: (sessionId: string) => void;
}

/** Score color: green >= 0.7, yellow >= 0.4, red < 0.4 */
function scoreColor(score: number | null): string {
  if (score === null || score === undefined) return "text-muted-foreground";
  if (score >= 0.7) return "text-green-600 dark:text-green-400";
  if (score >= 0.4) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-600 dark:text-red-400";
}

function formatScore(score: number | null): string {
  if (score === null || score === undefined) return "---";
  return score.toFixed(2);
}

export function SessionTable({ onSelectSession }: SessionTableProps) {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const { refreshKey } = useRefresh();

  useEffect(() => {
    let cancelled = false;
    getDashboardSessions(30)
      .then((d) => { if (!cancelled) setSessions(d); })
      .catch(() => { if (!cancelled) setSessions([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [refreshKey]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Chat Sessions</CardTitle>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
          </div>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground py-8 text-center">
            No sessions yet. Start chatting to see session analytics here.
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Session</TableHead>
                  <TableHead className="text-center">Messages</TableHead>
                  <TableHead className="text-center">Queries</TableHead>
                  <TableHead className="text-center">Faithfulness</TableHead>
                  <TableHead className="text-center">Context Prec.</TableHead>
                  <TableHead className="text-center">Avg Latency</TableHead>
                  <TableHead>Last Active</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((s) => (
                  <TableRow
                    key={s.session_id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => onSelectSession(s.session_id)}
                  >
                    <TableCell className="max-w-[220px]">
                      <div className="truncate font-medium">{s.title}</div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge variant="outline" className="text-[10px]">
                        {s.message_count}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">{s.total_queries}</TableCell>
                    <TableCell className={`text-center font-mono ${scoreColor(s.avg_faithfulness)}`}>
                      {formatScore(s.avg_faithfulness)}
                    </TableCell>
                    <TableCell className={`text-center font-mono ${scoreColor(s.avg_context_precision)}`}>
                      {formatScore(s.avg_context_precision)}
                    </TableCell>
                    <TableCell className="text-center">
                      {s.avg_latency_ms !== null ? `${Math.round(s.avg_latency_ms)}ms` : "---"}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(s.updated_at)}
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
