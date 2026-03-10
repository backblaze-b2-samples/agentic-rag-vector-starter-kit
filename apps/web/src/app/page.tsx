import { QuickStatus } from "@/components/dashboard/quick-status";
import { RetrievalQualityPanel } from "@/components/dashboard/retrieval-quality";
import { AgentBehaviorPanel } from "@/components/dashboard/agent-behavior";
import { RecentQueriesTable } from "@/components/dashboard/recent-queries-table";
import { IngestionPanel } from "@/components/dashboard/ingestion-panel";

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight">RAG Dashboard</h1>
      <QuickStatus />
      <div className="grid gap-6 lg:grid-cols-2">
        <RetrievalQualityPanel />
        <AgentBehaviorPanel />
      </div>
      <RecentQueriesTable />
      <IngestionPanel />
    </div>
  );
}
