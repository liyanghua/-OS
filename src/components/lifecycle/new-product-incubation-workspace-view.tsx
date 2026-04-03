"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toNewProductIncubationWorkspaceVm } from "@/domain/mappers/to-lifecycle-stage-workspace-vm";
import {
  riskLevelLabel,
  samplingStatusLabel,
} from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoApprovalRow } from "@/components/cards/ceo-approval-row";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { AgentStrip } from "@/components/lifecycle/workspace/agent-strip";

export function NewProductIncubationWorkspaceView() {
  const { projects, exceptions, roleView } = useAppStore();
  const vm = useMemo(
    () => toNewProductIncubationWorkspaceVm(projects, exceptions, roleView),
    [projects, exceptions, roleView],
  );
  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  const laneTitle = {
    onTrack: "正常推进",
    attention: "需关注",
    risk: "风险干预",
  } as const;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          新品孵化
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          将商机落地为可首发商品：泳道看健康度，定义与打样风险居中，会签待批不脱离项目对象。
        </p>
      </header>

      <ManagementPanel
        title="孵化脉冲"
        description="本阶段项目与关联例外；待批仅为本阶段内动作。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="孵化泳道（按健康度）"
        description="原型：健康度三分桶，便于您在会前扫一眼队伍状态。"
      >
        <div className="grid gap-4 lg:grid-cols-3">
          {(
            [
              ["onTrack", vm.swimlane.onTrack],
              ["attention", vm.swimlane.attention],
              ["risk", vm.swimlane.risk],
            ] as const
          ).map(([key, list]) => (
            <div
              key={key}
              className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3"
            >
              <h3 className="text-sm font-semibold text-[var(--foreground)]">
                {laneTitle[key]}
              </h3>
              <div className="mt-2 space-y-2">
                {list.length === 0 ? (
                  <p className="text-xs text-[var(--muted)]">暂无</p>
                ) : (
                  list.map((p) => <BattleProjectCard key={p.id} project={p} />)
                )}
              </div>
            </div>
          ))}
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="商品定义摘要"
        description="已挂商品定义的项目（定位、人群与规格摘要）。"
      >
        {vm.definitionHighlights.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无商品定义。</p>
        ) : (
          <ul className="space-y-3 text-xs">
            {vm.definitionHighlights.map((p) => (
              <li
                key={p.id}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <Link
                  href={`/projects/${p.id}`}
                  className="font-medium text-[var(--accent)] hover:underline"
                >
                  {p.name}
                </Link>
                {p.definition ? (
                  <dl className="mt-2 grid gap-1 text-[var(--muted)] sm:grid-cols-2">
                    <div>
                      <dt className="text-[var(--foreground)]">定位</dt>
                      <dd>{p.definition.positioning}</dd>
                    </div>
                    <div>
                      <dt className="text-[var(--foreground)]">人群</dt>
                      <dd>{p.definition.targetAudience}</dd>
                    </div>
                  </dl>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="打样风险"
        description="按可行性风险排序的候选（原型）。"
      >
        {vm.samplingRiskProjects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无带打样信息的项目。</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {vm.samplingRiskProjects.map((p) => (
              <li
                key={p.id}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <Link
                  href={`/projects/${p.id}`}
                  className="font-medium text-[var(--accent)]"
                >
                  {p.name}
                </Link>
                {p.definition ? (
                  <div className="mt-1 text-[var(--muted)]">
                    可行性风险 {riskLevelLabel(p.definition.feasibilityRisk)} ·
                    打样 {samplingStatusLabel(p.definition.samplingStatus)}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="会签与待批节点"
        description="本阶段来源的待审批动作。"
      >
        {vm.cosignPending.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无会签待批。</p>
        ) : (
          <div className="space-y-2">
            {vm.cosignPending.map((a) => (
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

      <ManagementPanel title="阻塞与例外" description="本阶段关联例外。">
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

      <ManagementPanel title="智能体进度" description="本阶段项目下智能体状态。">
        <AgentStrip agents={vm.agents} />
      </ManagementPanel>
    </div>
  );
}
