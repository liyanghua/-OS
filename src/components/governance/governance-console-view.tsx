"use client";

import Link from "next/link";
import { useMemo } from "react";
import { toGovernanceVm } from "@/domain/mappers/to-governance-vm";
import {
  confidenceLevelPercentLabel,
  riskLevelLabel,
} from "@/domain/mappers/display-zh";
import { exceptionSourceLabel } from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { OperatingLayerLegend } from "@/components/cards/operating-layer-badge";
import { CeoExceptionRow } from "@/components/cards/ceo-exception-row";
import { ActionHubActionRow } from "@/components/governance/action-hub-action-row";
import { PolicyBoundaryCard } from "@/components/governance/policy-boundary-card";
import { ExecutionLogRow } from "@/components/governance/execution-log-row";

export function GovernanceConsoleView() {
  const { projects, exceptions, policyBoundaries } = useAppStore();
  const vm = useMemo(
    () => toGovernanceVm(projects, exceptions, policyBoundaries),
    [projects, exceptions, policyBoundaries],
  );

  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          风险与审批台
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          例外优先：先看队列与规则边界，再收敛高风险待批与低置信建议；配套执行审计，而非制度配置后台。
        </p>
      </header>

      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface-elevated)]/50 p-4 ring-1 ring-white/[0.04]">
        <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
          协同分层说明（与动作中心、商品项目详情一致）
        </p>
        <OperatingLayerLegend />
      </div>

      <ManagementPanel
        title="例外队列"
        description="按严重度排序；需人工介入项在卡片内标出（与动作中心联动处置）。"
      >
        {vm.exceptions.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无例外。</p>
        ) : (
          <div className="space-y-2">
            {vm.exceptions.map((ex) => (
              <div key={ex.id}>
                <div className="mb-1 text-[10px] text-[var(--muted)]">
                  {exceptionSourceLabel(ex.source)} · {riskLevelLabel(ex.severity)}
                </div>
                <CeoExceptionRow
                  exception={ex}
                  projectName={
                    ex.projectId ? projectNameById[ex.projectId] : undefined
                  }
                />
              </div>
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="智能体异常"
        description="来源为智能体失败的例外拆条展示，便于排障与降级。"
      >
        {vm.agentAnomalies.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无智能体异常。</p>
        ) : (
          <div className="space-y-2">
            {vm.agentAnomalies.map((ex) => (
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
        title="规则边界命中"
        description="与政策/叠券等相关的例外条目。"
      >
        {vm.policyViolations.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无规则边界例外。</p>
        ) : (
          <div className="space-y-2">
            {vm.policyViolations.map((ex) => (
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
        title="高风险待审批"
        description="待批且风险为高/极高的动作，优先进入人在环路。"
      >
        {vm.highRiskApprovals.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <div className="space-y-2">
            {vm.highRiskApprovals.map((r) => (
              <ActionHubActionRow key={r.action.id} row={r} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="低置信度建议"
        description="决策对象置信度为「低」的条目，需要增强证据或人工结论。"
      >
        {vm.lowConfidenceDecisions.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {vm.lowConfidenceDecisions.map(({ decision: d, projectId, projectName }) => (
              <li
                key={d.id}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <Link
                  href={`/projects/${projectId}`}
                  className="font-medium text-[var(--accent)] hover:underline"
                >
                  {projectName}
                </Link>
                <p className="mt-1 text-[var(--foreground)]">
                  {d.problemOrOpportunity}
                </p>
                <p className="mt-1 text-[var(--muted)]">{d.rationale}</p>
                <p className="mt-1 text-[var(--muted)]">
                  AI 置信度 {confidenceLevelPercentLabel(d.confidence)}
                  {d.requiresHumanApproval ? " · 需人工确认" : ""}
                </p>
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="规则与策略边界（护栏）"
        description="全局策略护栏原型：硬阻断 / 需审批 / 仅告警。"
      >
        <div className="grid gap-2 sm:grid-cols-2">
          {vm.policyBoundaries.map((p) => (
            <PolicyBoundaryCard key={p.id} policy={p} />
          ))}
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="审计记录 · 执行流水"
        description="人为发起 / 智能体 / 自动化分别更新状态，每条留痕写清谁于何时改了什么。"
      >
        {vm.auditLogs.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无。</p>
        ) : (
          <div className="space-y-2">
            {vm.auditLogs.slice(0, 20).map((log) => (
              <ExecutionLogRow key={log.id} log={log} />
            ))}
          </div>
        )}
      </ManagementPanel>
    </div>
  );
}
