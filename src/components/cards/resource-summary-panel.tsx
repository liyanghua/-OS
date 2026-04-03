import type { CEODashboardVM } from "@/domain/types";
import { ManagementPanel } from "@/components/cards/management-panel";

type ResourceSummaryPanelProps = {
  resource: CEODashboardVM["resourceSummary"];
};

export function ResourceSummaryPanel({ resource }: ResourceSummaryPanelProps) {
  return (
    <ManagementPanel
      title="资源配置"
      description="原型摘要：与当前 mock 规模挂钩，不接真实金额与编制。"
    >
      <div className="space-y-2 text-xs text-[var(--foreground)]">
        <p>
          <span className="font-medium text-[var(--muted)]">预算与投放：</span>
          {resource.budgetSummary}
        </p>
        <p>
          <span className="font-medium text-[var(--muted)]">团队与容量：</span>
          {resource.teamCapacitySummary}
        </p>
        <p>
          <span className="font-medium text-[var(--muted)]">智能体容量：</span>
          {resource.agentCapacitySummary}
        </p>
      </div>
    </ManagementPanel>
  );
}
