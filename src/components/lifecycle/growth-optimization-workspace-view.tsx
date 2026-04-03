"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toGrowthOptimizationWorkspaceVm } from "@/domain/mappers/to-lifecycle-stage-workspace-vm";
import {
  approvalStatusLabel,
  executionStatusLabel,
  triggeredByLabel,
} from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { AgentStrip } from "@/components/lifecycle/workspace/agent-strip";

export function GrowthOptimizationWorkspaceView() {
  const { projects, exceptions, roleView } = useAppStore();
  const vm = useMemo(
    () => toGrowthOptimizationWorkspaceVm(projects, exceptions, roleView),
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
          增长优化
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          诊断—优化动作—作战区一体：例外与脉冲在先，动作与智能体跟进，面向放量经营拆解。
        </p>
      </header>

      <ManagementPanel
        title="增长脉冲"
        description="本阶段项目、例外与待批的合成视图。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="经营诊断"
        description="例外摘要 + 项目脉冲/阻塞条目（原型拼贴）。"
      >
        <ul className="space-y-2 text-xs text-[var(--foreground)]">
          {vm.diagnosisItems.map((line, i) => (
            <li
              key={i}
              className="rounded-md border border-[var(--border)] px-3 py-2"
            >
              {line}
            </li>
          ))}
        </ul>
      </ManagementPanel>

      <ManagementPanel
        title="增长作战区"
        description="本阶段在盘商品项目。"
      >
        {vm.projects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.projects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="优化动作"
        description="待审批优先列出；来源标签区分人为/经营建议/智能体/自动化。"
      >
        {vm.optimizationActions.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无动作。</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {vm.optimizationActions.map((a) => (
              <li
                key={a.id}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <div className="font-medium text-[var(--foreground)]">
                  {a.title}
                </div>
                <div className="mt-1 flex flex-wrap gap-2 text-[var(--muted)]">
                  <span>{triggeredByLabel(a.triggeredBy)}</span>
                  <span>{approvalStatusLabel(a.approvalStatus)}</span>
                  <span>{executionStatusLabel(a.executionStatus)}</span>
                </div>
                <p className="mt-1 text-[var(--muted)]">{a.summary}</p>
                <Link
                  href={`/projects/${a.sourceProjectId}`}
                  className="mt-1 inline-block text-[var(--accent)] hover:underline"
                >
                  所属项目：
                  {projectNameById[a.sourceProjectId] ?? a.sourceProjectId}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel title="阻塞与例外" description="增长阶段关联例外。">
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

      <ManagementPanel title="智能体状态" description="增长战线智能体摘要。">
        <AgentStrip agents={vm.agents} />
      </ManagementPanel>
    </div>
  );
}
