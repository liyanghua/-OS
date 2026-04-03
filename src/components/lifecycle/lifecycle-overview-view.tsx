"use client";

import Link from "next/link";
import { useMemo } from "react";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import type { LifecycleStage, ProjectObject } from "@/domain/types";
import { toLifecycleOverviewVm } from "@/domain/mappers/to-lifecycle-overview-vm";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { agentStatusLabel } from "@/domain/mappers/display-zh";
import { AgentStatusIndicator } from "@/components/ui/agent-status-indicator";

const STAGE_ORDER: LifecycleStage[] = [
  "opportunity_pool",
  "new_product_incubation",
  "launch_validation",
  "growth_optimization",
  "legacy_upgrade",
  "review_capture",
];


const HEALTH_PRIOR: Record<ProjectObject["health"], number> = {
  critical: 4,
  at_risk: 3,
  watch: 2,
  healthy: 1,
};

function pickWalkthroughRepresentative(
  projects: ProjectObject[],
): ProjectObject | null {
  if (projects.length === 0) return null;
  const withBlocker = projects.filter((p) => p.keyBlocker);
  const pool = withBlocker.length > 0 ? withBlocker : projects;
  return [...pool].sort(
    (a, b) =>
      HEALTH_PRIOR[b.health] - HEALTH_PRIOR[a.health] || b.priority - a.priority,
  )[0];
}

function stageWorkspaceHref(stage: LifecycleStage): string {
  if (stage === "opportunity_pool") return "/lifecycle/opportunity-pool";
  if (stage === "new_product_incubation") return "/lifecycle/new-product-incubation";
  if (stage === "launch_validation") return "/lifecycle/launch-validation";
  if (stage === "growth_optimization") return "/lifecycle/growth-optimization";
  if (stage === "legacy_upgrade") return "/lifecycle/legacy-upgrade";
  return "/lifecycle/review-capture";
}


export function LifecycleOverviewView() {
  const { projects, exceptions } = useAppStore();
  const vm = useMemo(
    () => toLifecycleOverviewVm(projects, exceptions),
    [projects, exceptions],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          商品经营主线总览
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          以商品经营阶段为主轴，查看分布、健康度、阻塞问题、待审批与智能体活跃概要（数据来自当前 mock
          存储，后续可接实时层）。
        </p>
      </header>


      <ManagementPanel
        title="走查快速进入项目"
        description="每一阶段优选一个代表项目（优先带关键阻塞，其次健康度与优先级）；附该阶段 Top 风险与 Top 阻塞摘要，便于老板与总监走查。"
      >
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {STAGE_ORDER.map((stage) => {
            const projs = vm.stageProjects[stage];
            const rep = pickWalkthroughRepresentative(projs);
            const topRisk = vm.stageBlockers[stage][0]?.summary;
            const topBlockProject = projs.find((p) => p.keyBlocker);
            const topBlock = topBlockProject?.keyBlocker;
            return (
              <div
                key={stage}
                className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-3 text-xs"
              >
                <p className="font-medium text-[var(--foreground)]">
                  {LIFECYCLE_STAGE_LABELS[stage]}
                </p>
                {rep ? (
                  <p className="mt-2 text-[var(--muted)]">
                    代表项目：
                    <Link
                      href={`/projects/${rep.id}`}
                      className="font-medium text-[var(--accent)] hover:underline"
                    >
                      {rep.name}
                    </Link>
                  </p>
                ) : (
                  <p className="mt-2 text-[var(--muted)]">该阶段暂无在盘项目。</p>
                )}
                <p className="mt-1.5 text-[var(--muted)]">
                  <span className="text-[var(--foreground)]">Top 风险：</span>
                  {topRisk ?? "—"}
                </p>
                <p className="mt-1 text-[var(--muted)]">
                  <span className="text-[var(--foreground)]">Top 阻塞：</span>
                  {topBlock ?? "—"}
                </p>
                <p className="mt-2">
                  <Link
                    href={stageWorkspaceHref(stage)}
                    className="text-[var(--accent)] hover:underline"
                  >
                    进入阶段工作台 →
                  </Link>
                </p>
              </div>
            );
          })}
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="阶段项目分布"
        description="各阶段商品项目数量，点击进入对应阶段工作台。"
      >
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {STAGE_ORDER.map((stage) => {
            const count = vm.stageCounts[stage];
            const href =
              stage === "opportunity_pool"
                ? "/lifecycle/opportunity-pool"
                : stage === "new_product_incubation"
                  ? "/lifecycle/new-product-incubation"
                  : stage === "launch_validation"
                    ? "/lifecycle/launch-validation"
                    : stage === "growth_optimization"
                      ? "/lifecycle/growth-optimization"
                      : stage === "legacy_upgrade"
                        ? "/lifecycle/legacy-upgrade"
                        : "/lifecycle/review-capture";
            return (
              <Link
                key={stage}
                href={href}
                className="flex items-center justify-between rounded-md border border-[var(--border)] px-3 py-2 text-sm transition-colors hover:border-[var(--accent)]"
              >
                <span className="text-[var(--foreground)]">
                  {LIFECYCLE_STAGE_LABELS[stage]}
                </span>
                <span className="font-medium text-[var(--accent)]">{count}</span>
              </Link>
            );
          })}
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="阶段健康度摘要"
        description="按阶段汇总商品项目健康标签分布。"
      >
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-left text-xs">
            <thead>
              <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                <th className="pb-2 pr-3 font-medium">阶段</th>
                <th className="pb-2 pr-2">健康</th>
                <th className="pb-2 pr-2">关注</th>
                <th className="pb-2 pr-2">有风险</th>
                <th className="pb-2">高风险</th>
              </tr>
            </thead>
            <tbody>
              {STAGE_ORDER.map((stage) => {
                const h = vm.stageHealthSummary[stage];
                return (
                  <tr
                    key={stage}
                    className="border-b border-[var(--border)]/60 text-[var(--foreground)]"
                  >
                    <td className="py-2 pr-3">
                      {LIFECYCLE_STAGE_LABELS[stage]}
                    </td>
                    <td className="py-2 pr-2">{h.healthy}</td>
                    <td className="py-2 pr-2">{h.watch}</td>
                    <td className="py-2 pr-2">{h.atRisk}</td>
                    <td className="py-2">{h.critical}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="阻塞与例外"
        description="含例外队列及标注了关键阻塞的商品项目。未关联项目的全站例外归在复盘沉淀阶段列示。"
      >
        {(() => {
          const rows = STAGE_ORDER.map((stage) => {
            const blockers = vm.stageBlockers[stage];
            const label = LIFECYCLE_STAGE_LABELS[stage];
            const kb = vm.stageProjects[stage].filter((p) => p.keyBlocker);
            if (blockers.length === 0 && kb.length === 0) return null;
            return (
              <li key={stage}>
                <p className="font-medium text-[var(--foreground)]">{label}</p>
                <ul className="mt-1 list-inside list-disc text-[var(--muted)]">
                  {blockers.map((e) => (
                    <li key={e.id}>{e.summary}</li>
                  ))}
                  {kb.map((p) => (
                    <li key={p.id}>
                      <Link
                        href={`/projects/${p.id}`}
                        className="text-[var(--accent)] hover:underline"
                      >
                        {p.name}
                      </Link>
                      ：{p.keyBlocker}
                    </li>
                  ))}
                </ul>
              </li>
            );
          }).filter(Boolean);
          return rows.length > 0 ? (
            <ul className="space-y-3 text-sm">{rows}</ul>
          ) : (
            <p className="text-sm text-[var(--muted)]">暂无阻塞与例外</p>
          );
        })()}
      </ManagementPanel>

      <ManagementPanel
        title="待审批动作（按阶段）"
        description="来源于各商品项目下的待审批动作。"
      >
        <ul className="space-y-3 text-sm">
          {STAGE_ORDER.map((stage) => {
            const acts = vm.stageApprovals[stage];
            if (acts.length === 0) return null;
            return (
              <li key={stage}>
                <p className="font-medium text-[var(--foreground)]">
                  {LIFECYCLE_STAGE_LABELS[stage]}
                </p>
                <ul className="mt-1 list-inside list-disc text-[var(--muted)]">
                  {acts.map((a) => (
                    <li key={a.id}>
                      {a.title}
                      <Link
                        href={`/projects/${a.sourceProjectId}`}
                        className="ml-1 text-[var(--accent)] hover:underline"
                      >
                        查看项目
                      </Link>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      </ManagementPanel>

      <ManagementPanel
        title="智能体活跃（骨架）"
        description="聚合各阶段商品项目的智能体状态，后续可替换为实时订阅。"
      >
        <ul className="space-y-2 text-base text-[var(--muted)]">
          {STAGE_ORDER.map((stage) => {
            const projs = vm.stageProjects[stage];
            const active = projs.flatMap((p) =>
              p.agentStates.map((g) => ({
                projectId: p.id,
                projectName: p.name,
                agent: g,
              })),
            );
            if (active.length === 0) return null;
            return (
              <li key={stage}>
                <span className="font-medium text-[var(--foreground)]">
                  {LIFECYCLE_STAGE_LABELS[stage]}
                </span>
                <ul className="mt-1 ml-3 list-disc space-y-1">
                  {active.map(({ projectId, projectName, agent }) => (
                    <li key={agent.id} className="flex flex-wrap items-start gap-2">
                      <AgentStatusIndicator status={agent.status} />
                      <span>
                        <Link
                          href={`/projects/${projectId}`}
                          className="font-medium text-[var(--accent)] hover:underline"
                        >
                          {projectName}
                        </Link>
                        <span className="text-[var(--foreground)]">
                          {" "}
                          · {agentStatusLabel(agent.status)}
                        </span>
                        <span className="text-[var(--muted)]"> — {agent.summary}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      </ManagementPanel>
    </div>
  );
}
