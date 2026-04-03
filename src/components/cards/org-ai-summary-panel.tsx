import type { CEODashboardVM } from "@/domain/types";
import { ManagementPanel } from "@/components/cards/management-panel";

type OrgAiSummaryPanelProps = {
  orgAI: CEODashboardVM["orgAISummary"];
};

export function OrgAiSummaryPanel({ orgAI }: OrgAiSummaryPanelProps) {
  return (
    <ManagementPanel
      title="组织与 AI 效能"
      description="原型摘要：强调人在环路与决策到执行路径，非通用 KPI 墙。"
    >
      <div className="space-y-2 text-xs text-[var(--foreground)]">
        <p>
          <span className="font-medium text-[var(--muted)]">决策到执行：</span>
          {orgAI.decisionToExecutionCycle}
        </p>
        <p>
          <span className="font-medium text-[var(--muted)]">AI 采用：</span>
          {orgAI.aiAdoptionSummary}
        </p>
        <p>
          <span className="font-medium text-[var(--muted)]">自动化覆盖：</span>
          {orgAI.automationCoverageSummary}
        </p>
      </div>
    </ManagementPanel>
  );
}
