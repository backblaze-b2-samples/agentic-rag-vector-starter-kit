"use client";

import { useState } from "react";
import { QuickStatus } from "@/components/dashboard/quick-status";
import { KnowledgeBase } from "@/components/dashboard/knowledge-base";
import { SessionTable } from "@/components/dashboard/session-table";
import { SessionDetail } from "@/components/dashboard/session-detail";
import { RetrievalQualityPanel } from "@/components/dashboard/retrieval-quality";
import { AgentBehaviorPanel } from "@/components/dashboard/agent-behavior";

export default function DashboardPage() {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">Agentic RAG Dashboard</h1>
      <QuickStatus />
      <KnowledgeBase />

      {/* Session analytics: table → drill-down */}
      {selectedSessionId ? (
        <SessionDetail
          sessionId={selectedSessionId}
          onBack={() => setSelectedSessionId(null)}
        />
      ) : (
        <SessionTable onSelectSession={setSelectedSessionId} />
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <RetrievalQualityPanel />
        <AgentBehaviorPanel />
      </div>
    </div>
  );
}
