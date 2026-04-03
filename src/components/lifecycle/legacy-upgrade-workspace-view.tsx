"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toLegacyUpgradeWorkspaceVm } from "@/domain/mappers/to-lifecycle-stage-workspace-vm";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoApprovalRow } from "@/components/cards/ceo-approval-row";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { AgentStrip } from "@/components/lifecycle/workspace/agent-strip";

export function LegacyUpgradeWorkspaceView() {
  const { projects, exceptions, roleView } = useAppStore();
  const vm = useMemo(
    () => toLegacyUpgradeWorkspaceVm(projects, exceptions, roleView),
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
          老品升级
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          升级候选与方向澄清先行，再上市验证骨架支持您安排验证窗口。
        </p>
      </header>

      <ManagementPanel
        title="升级脉冲"
        description="本阶段项目与关联例外。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="升级候选"
        description="老品升级在盘商品项目。"
      >
        {vm.projects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无老品升级项目。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.projects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="升级方向"
        description="决策 rationale / 视觉简报 / 目标摘要（优先级递减，原型）。"
      >
        {vm.upgradeDirections.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {vm.upgradeDirections.map((row) => (
              <li
                key={row.projectId}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <Link
                  href={`/projects/${row.projectId}`}
                  className="font-medium text-[var(--accent)] hover:underline"
                >
                  {row.name}
                </Link>
                <p className="mt-1 text-[var(--muted)]">{row.directionLine}</p>
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="再上市验证（骨架）"
        description="占位清单：后续可接数据与门禁，不阻塞当前原型。"
      >
        <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--foreground)]">
          {vm.relaunchValidationBullets.map((b, i) => (
            <li key={i}>{b}</li>
          ))}
        </ul>
      </ManagementPanel>

      <ManagementPanel title="待审批" description="老品升级阶段待批。">
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

      <ManagementPanel title="阻塞与例外" description="关联本阶段。">
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

      <ManagementPanel title="智能体与协同" description="本阶段智能体摘要。">
        <AgentStrip agents={vm.agents} />
      </ManagementPanel>
    </div>
  );
}
