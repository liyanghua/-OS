"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toOpportunityPoolWorkspaceVm } from "@/domain/mappers/to-lifecycle-stage-workspace-vm";
import {
  confidenceLevelPercentLabel,
  opportunityRecommendationLabel,
  projectHealthLabel,
  riskLevelLabel,
} from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { CeoApprovalRow } from "@/components/cards/ceo-approval-row";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { AgentStrip } from "@/components/lifecycle/workspace/agent-strip";

export function OpportunityPoolWorkspaceView() {
  const { projects, exceptions, roleView } = useAppStore();
  const vm = useMemo(
    () => toOpportunityPoolWorkspaceVm(projects, exceptions, roleView),
    [projects, exceptions, roleView],
  );
  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  const agents = useMemo(
    () => vm.projects.flatMap((p) => p.agentStates.map((state) => ({ state, project: p }))),
    [vm.projects],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">商机池</h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          发现与评估商机信号，排序后转化为商品项目。本页为阶段工作台：脉冲优先、机会卡与待决策并列。
        </p>
      </header>

      <ManagementPanel
        title="机会脉冲"
        description="仅包含本阶段项目及关联例外；无 projectId 的全局例外不在此列。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="商机作战区"
        description="商机阶段在盘商品项目，可进入详情深化评估。"
      >
        {vm.projects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无商机池项目。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.projects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="机会评分与建议立项"
        description="经营侧评估摘要（AI/规则原型）；最终以您拍板为准。"
      >
        {vm.projects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无数据。</p>
        ) : (
          <ul className="space-y-3">
            {vm.projects.map((p) => (
              <li
                key={p.id}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-xs"
              >
                <div className="font-medium text-[var(--foreground)]">
                  <Link
                    href={`/projects/${p.id}`}
                    className="hover:text-[var(--accent)]"
                  >
                    {p.name}
                  </Link>
                </div>
                <div className="mt-1 text-[var(--muted)]">
                  健康 {projectHealthLabel(p.health)} · 风险{" "}
                  {riskLevelLabel(p.riskLevel)}
                </div>
                {p.opportunityAssessment ? (
                  <dl className="mt-2 grid gap-1 text-[var(--muted)] sm:grid-cols-2">
                    <div>
                      <dt className="inline text-[var(--foreground)]">商业价值</dt>{" "}
                      <dd className="inline">
                        {p.opportunityAssessment.businessValueScore}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline text-[var(--foreground)]">可行性</dt>{" "}
                      <dd className="inline">
                        {p.opportunityAssessment.feasibilityScore}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline text-[var(--foreground)]">表达潜力</dt>{" "}
                      <dd className="inline">
                        {p.opportunityAssessment.expressionPotentialScore}
                      </dd>
                    </div>
                    <div>
                      <dt className="inline text-[var(--foreground)]">置信度</dt>{" "}
                      <dd className="inline tabular-nums">
                        {confidenceLevelPercentLabel(
                          p.opportunityAssessment.confidence,
                        )}
                      </dd>
                    </div>
                    <div className="sm:col-span-2">
                      <span className="text-[var(--foreground)]">建议</span>
                      ：{opportunityRecommendationLabel(
                        p.opportunityAssessment.recommendation,
                      )}
                    </div>
                  </dl>
                ) : (
                  <p className="mt-2 text-[var(--muted)]">暂无结构化商机评估。</p>
                )}
                {p.opportunitySignals && p.opportunitySignals.length > 0 ? (
                  <ul className="mt-2 space-y-1 border-t border-[var(--border)] pt-2">
                    {p.opportunitySignals.map((s) => (
                      <li key={s.id}>
                        {s.summary}（强度 {s.strength}）
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="待审批与经营决策"
        description="商机阶段待批动作（含经营侧建议触发项）。"
      >
        {vm.pendingApprovals.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无待审批。</p>
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

      <ManagementPanel
        title="阻塞与例外"
        description="关联本阶段项目的经营例外。"
      >
        {vm.blockers.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无关联例外。</p>
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

      <ManagementPanel
        title="智能体与采集进度"
        description="场景智能体运行摘要（非聊天壳）。"
      >
        <AgentStrip agents={agents} />
      </ManagementPanel>
    </div>
  );
}
