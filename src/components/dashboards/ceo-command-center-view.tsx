"use client";

import Link from "next/link";
import { WalkthroughHintPanel } from "@/components/shell/walkthrough-hint-panel";
import { useMemo } from "react";
import { toCeoDashboardVm } from "@/domain/mappers/to-ceo-dashboard-vm";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoApprovalRow } from "@/components/cards/ceo-approval-row";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { ResourceSummaryPanel } from "@/components/cards/resource-summary-panel";
import { OrgAiSummaryPanel } from "@/components/cards/org-ai-summary-panel";

export function CeoCommandCenterView() {
  const { projects, exceptions } = useAppStore();
  const vm = useMemo(
    () => toCeoDashboardVm(projects, exceptions),
    [projects, exceptions],
  );
  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          老板经营指挥台
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          以经营脉冲为先：例外、阻塞与待审批前置；再下钻关键战役与资源配置。数据来自当前
          mock，人机协作标签区分人为发起、经营建议、智能体与自动化。
        </p>
      </header>

      <ManagementPanel
        title="经营脉冲"
        description="今日信号摘要与分项列表，类别与风险强度已本地化展示。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
        <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--border)]/50 pt-4">
          <Link
            href="/action-hub?focus=pending"
            className="inline-flex items-center rounded-md bg-[var(--accent)] px-3 py-2 text-xs font-semibold text-[var(--accent-foreground)] shadow-sm hover:opacity-90"
          >
            处理待审批收口
          </Link>
          <Link
            href="/governance"
            className="inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--surface-elevated)]/60 px-3 py-2 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--border)]/25"
          >
            打开风险与审批台
          </Link>
        </div>
      </ManagementPanel>

      <WalkthroughHintPanel variant="ceo" defaultCollapsed />

      <ManagementPanel
        title="关键战役"
        description="按阶段势能、健康度与优先级排序的商品项目 Top 列表，可进入项目详情。"
      >
        <div className="grid gap-2 sm:grid-cols-2">
          {vm.topProjects.map((p) => (
            <BattleProjectCard key={p.id} project={p} />
          ))}
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="重点风险与待审批"
        description="全局例外与待批动作并列，高风险与需您拍板项优先展示。"
      >
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              经营例外
            </h3>
            {vm.topExceptions.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">暂无高优先例外。</p>
            ) : (
              <>
                {vm.topExceptions.slice(0, 2).map((ex) => (
                  <CeoExceptionRow
                    key={ex.id}
                    exception={ex}
                    projectName={
                      ex.projectId ? projectNameById[ex.projectId] : undefined
                    }
                  />
                ))}
                {vm.topExceptions.length > 2 ? (
                  <p className="pt-1">
                    <Link
                      href="/governance"
                      className="text-xs font-medium text-[var(--accent)] hover:underline"
                    >
                      查看全部 {vm.topExceptions.length} 条例外 →
                    </Link>
                  </p>
                ) : null}
              </>
            )}
          </div>
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              待审批动作
            </h3>
            {vm.topApprovals.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">暂无待审批项。</p>
            ) : (
              <>
                {vm.topApprovals.slice(0, 2).map((a) => (
                  <CeoApprovalRow
                    key={a.id}
                    action={a}
                    projectName={
                      projectNameById[a.sourceProjectId] ?? a.sourceProjectId
                    }
                  />
                ))}
                {vm.topApprovals.length > 2 ? (
                  <p className="pt-1">
                    <Link
                      href="/action-hub?focus=pending"
                      className="text-xs font-medium text-[var(--accent)] hover:underline"
                    >
                      查看全部待审批 →
                    </Link>
                  </p>
                ) : null}
              </>
            )}
          </div>
        </div>
      </ManagementPanel>

      <div className="grid gap-6 lg:grid-cols-2">
        <ResourceSummaryPanel resource={vm.resourceSummary} />
        <OrgAiSummaryPanel orgAI={vm.orgAISummary} />
      </div>
    </div>
  );
}
