"use client";

import { useMemo } from "react";
import { toLaunchValidationWorkspaceVm } from "@/domain/mappers/to-lifecycle-stage-workspace-vm";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoApprovalRow } from "@/components/cards/ceo-approval-row";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { GrowthPlanCompareBlock } from "@/components/cards/growth-plan-compare-block";
import { AgentStrip } from "@/components/lifecycle/workspace/agent-strip";

export function LaunchValidationWorkspaceView() {
  const { projects, exceptions, roleView } = useAppStore();
  const vm = useMemo(
    () => toLaunchValidationWorkspaceVm(projects, exceptions, roleView),
    [projects, exceptions, roleView],
  );
  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          首发验证
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          目标对结果、版本对比与放量/调整/暂停建议并列，支撑首发窗口内的经营决策。
        </p>
      </header>

      <ManagementPanel
        title="首发脉冲"
        description="本阶段项目、例外与待批的合成脉冲。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="作战区：首发在盘项目"
        description="点击进入商品项目详情，查看表达与动作全量。"
      >
        {vm.projects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无首发验证项目。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.projects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="目标 vs 结果"
        description="经营目标摘要与 KPI 快览（mock 指标）。"
      >
        {vm.targetVsResult.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {vm.targetVsResult.map((row) => (
              <li
                key={row.projectId}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <p className="font-medium text-[var(--foreground)]">
                  {row.name}
                </p>
                <p className="mt-1 text-[var(--muted)]">
                  目标：{row.targetSummary}
                </p>
                <p className="mt-1 text-[var(--foreground)]">
                  结果快览：{row.kpiSummary}
                </p>
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="版本对比"
        description="存在多主图/多决策枝时的快捷比对（原型规则同增长台方案对比）。"
      >
        <GrowthPlanCompareBlock projects={vm.planCompareProjects} />
      </ManagementPanel>

      <ManagementPanel
        title="放量 / 调整 / 暂停建议"
        description="经营侧建议摘要、待决策动作与实时脉冲拼贴（不替代正式审批）。"
      >
        {vm.scaleAdjustPauseHints.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无建议条目。</p>
        ) : (
          <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--foreground)]">
            {vm.scaleAdjustPauseHints.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel title="待审批" description="首发阶段待批动作。">
        {vm.pendingApprovals.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <div className="space-y-2">
            {vm.pendingApprovals.map((a) => (
              <CeoApprovalRow
                key={a.id}
                action={a}
                projectName={
                  projectNameById[a.sourceProjectId] ?? a.sourceProjectId
                }
              />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel title="阻塞与例外" description="关联本阶段项目。">
        {vm.blockers.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <div className="space-y-2">
            {vm.blockers.map((ex) => (
              <CeoExceptionRow
                key={ex.id}
                exception={ex}
                projectName={
                  ex.projectId ? projectNameById[ex.projectId] : undefined
                }
              />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel title="智能体与实时诊断" description="首发窗口内智能体摘要。">
        <AgentStrip agents={vm.agents} />
      </ManagementPanel>
    </div>
  );
}
