"use client";

import Link from "next/link";
import { WalkthroughHintPanel } from "@/components/shell/walkthrough-hint-panel";
import { useMemo } from "react";
import { toGrowthDirectorVm } from "@/domain/mappers/to-growth-vm";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoApprovalRow } from "@/components/cards/ceo-approval-row";
import {
  GrowthPlanCompareBlock,
  planCompareProjects,
} from "@/components/cards/growth-plan-compare-block";
import {
  groupBlockersByStage,
  GrowthBlockerMap,
} from "@/components/cards/growth-blocker-map";
import { GrowthAgentStatusBlock } from "@/components/cards/growth-agent-status-block";
import { GrowthDualStageRail } from "@/components/cards/growth-dual-stage-rail";

export function GrowthDirectorView() {
  const { projects, exceptions } = useAppStore();
  const vm = useMemo(
    () => toGrowthDirectorVm(projects, exceptions),
    [projects, exceptions],
  );

  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  const compareList = useMemo(
    () => planCompareProjects(vm.launchProjects, vm.optimizationProjects),
    [vm.launchProjects, vm.optimizationProjects],
  );

  const blockersGrouped = useMemo(
    () => groupBlockersByStage(vm.blockers, projects),
    [vm.blockers, projects],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          运营与营销总监工作台
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          增长脉冲优先：首发与放量项目、方案对比、待审批与阻塞地图并列；智能体状态为骨架，后续接实时编排。
        </p>
      </header>

      <ManagementPanel
        title="增长脉冲"
        description="侧重首发验证与增长优化战线的信号排序。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
        <div className="mt-4 flex flex-wrap gap-2 border-t border-[var(--border)]/50 pt-4">
          <Link
            href="/action-hub?focus=pending"
            className="inline-flex items-center rounded-md bg-[var(--accent)] px-3 py-2 text-xs font-semibold text-[var(--accent-foreground)] shadow-sm hover:opacity-90"
          >
            查看待审批动作（增长相关）
          </Link>
          <Link
            href="/governance"
            className="inline-flex items-center rounded-md border border-[var(--border)] bg-[var(--surface-elevated)]/60 px-3 py-2 text-xs font-medium text-[var(--foreground)] hover:bg-[var(--border)]/25"
          >
            打开风险与审批台
          </Link>
        </div>
      </ManagementPanel>

      <WalkthroughHintPanel variant="growth" defaultCollapsed />

      <ManagementPanel
        title="方案对比（分析区）"
        description="紧随增长脉冲：同一项目中存在多条决策选项或多个视觉版本时列出，用于管理前台比对；与下方战役列表分层留白。"
      >
        <GrowthPlanCompareBlock projects={compareList} />
      </ManagementPanel>

      <ManagementPanel
        title="首发 / 增长项目"
        description="分列首发验证与增长优化在盘项目。"
      >
        <GrowthDualStageRail
          launchCount={vm.launchProjects.length}
          growthCount={vm.optimizationProjects.length}
        />
        <div className="space-y-4">
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              首发验证
            </h3>
            {vm.launchProjects.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">暂无首发验证项目。</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {vm.launchProjects.map((p) => (
                  <BattleProjectCard key={p.id} project={p} />
                ))}
              </div>
            )}
          </div>
          <div>
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
              增长优化
            </h3>
            {vm.optimizationProjects.length === 0 ? (
              <p className="text-xs text-[var(--muted)]">暂无增长优化项目。</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {vm.optimizationProjects.map((p) => (
                  <BattleProjectCard key={p.id} project={p} />
                ))}
              </div>
            )}
          </div>
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="待审批动作"
        description="全量待批中按风险与是否需人工审批排序的条目。"
      >
        {vm.pendingApprovals.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无待审批动作。</p>
        ) : (
          <div className="space-y-2">
            {vm.pendingApprovals.slice(0, 2).map((a) => (
              <CeoApprovalRow
                key={a.id}
                action={a}
                projectName={
                  projectNameById[a.sourceProjectId] ?? a.sourceProjectId
                }
              />
            ))}
            {vm.pendingApprovals.length > 2 ? (
              <p className="pt-1">
                <Link
                  href="/action-hub?focus=pending"
                  className="text-xs font-medium text-[var(--accent)] hover:underline"
                >
                  查看全部 {vm.pendingApprovals.length} 条待审批 →
                </Link>
              </p>
            ) : null}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="阻塞地图"
        description="例外按所属项目阶段分组；无关联项目的条目归入复盘沉淀。"
      >
        <GrowthBlockerMap grouped={blockersGrouped} />
      </ManagementPanel>

      <ManagementPanel
        title="智能体状态"
        description="聚合首发与增长项目下的智能体状态（原型）。"
      >
        <GrowthAgentStatusBlock
          launchProjects={vm.launchProjects}
          optimizationProjects={vm.optimizationProjects}
        />
      </ManagementPanel>
    </div>
  );
}
