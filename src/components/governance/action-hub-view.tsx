"use client";

import Link from "next/link";
import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  toActionHubVm,
  toActionHubVmForProject,
} from "@/domain/mappers/to-action-hub-vm";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { OperatingLayerLegend } from "@/components/cards/operating-layer-badge";
import { ActionHubActionRow } from "@/components/governance/action-hub-action-row";
import { ExecutionLogRow } from "@/components/governance/execution-log-row";
import { ApprovalDrawer } from "@/components/governance/approval-drawer";
import { ActionDetailDrawer } from "@/components/governance/action-detail-drawer";
import {
  ActionHubProgressRail,
  type ActionHubRailSegment,
} from "@/components/governance/action-hub-progress-rail";
import type { ActionHubRow } from "@/domain/types";
import { approvalStatusLabel } from "@/domain/mappers/display-zh";
import { PulseIndicator } from "@/components/ui/pulse-indicator";

export function ActionHubView() {
  const searchParams = useSearchParams();
  const projectId = searchParams.get("projectId") ?? undefined;
  const focus = searchParams.get("focus") ?? undefined;

  const { projects } = useAppStore();

  const projectMeta = useMemo(() => {
    if (!projectId) return null;
    return projects.find((p) => p.id === projectId) ?? null;
  }, [projects, projectId]);

  const vm = useMemo(() => {
    if (projectId) {
      const scoped = toActionHubVmForProject(projects, projectId);
      if (scoped) return scoped;
    }
    return toActionHubVm(projects);
  }, [projects, projectId]);

  const projectMissing = Boolean(projectId && !projectMeta);

  const hubQueryBase =
    projectId != null
      ? `/action-hub?projectId=${encodeURIComponent(projectId)}`
      : "/action-hub";
  const hubQueryPending =
    projectId != null
      ? `/action-hub?projectId=${encodeURIComponent(projectId)}&focus=pending`
      : "/action-hub?focus=pending";

  const [approvalRow, setApprovalRow] = useState<ActionHubRow | null>(null);
  const [detailRow, setDetailRow] = useState<ActionHubRow | null>(null);
  const [legendOpen, setLegendOpen] = useState(false);

  const scrollToSection = useCallback((sectionId: string) => {
    document
      .getElementById(sectionId)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const railSegments: ActionHubRailSegment[] = useMemo(
    () => [
      { id: "action-hub-pending", label: "待审批", count: vm.pendingApprovals.length },
      { id: "action-hub-agent", label: "智能体监控", count: vm.agentMonitoring.length },
      { id: "action-hub-in-progress", label: "执行中", count: vm.inProgress.length },
      { id: "action-hub-high-risk", label: "高风险", count: vm.highRisk.length },
      { id: "action-hub-auto", label: "已自动", count: vm.autoExecuted.length },
      { id: "action-hub-completed", label: "已回写", count: vm.completed.length },
      { id: "action-hub-rolled", label: "已回滚", count: vm.rolledBack.length },
      {
        id: "action-hub-approval-audit",
        label: "审批留痕",
        count: vm.approvalAuditTrail.length,
      },
      { id: "action-hub-execution", label: "执行流水", count: vm.executionFeed.length },
    ],
    [vm],
  );

  const section = (
    panelId: string,
    title: string,
    description: string,
    rows: ActionHubRow[],
  ) => (
    <ManagementPanel id={panelId} title={title} description={description}>
      {rows.length === 0 ? (
        <p className="text-xs text-[var(--muted)]">暂无条目。</p>
      ) : (
        <div className="space-y-2">
          {rows.map((r) => (
            <ActionHubActionRow
              key={r.action.id}
              row={r}
              compact
              onOpenApproval={setApprovalRow}
              onOpenDetail={setDetailRow}
            />
          ))}
        </div>
      )}
    </ManagementPanel>
  );

  const executionPanel = (
    <ManagementPanel
      id="action-hub-execution"
      title="审计记录 · 执行流水"
      description="人为发起 / 智能体 / 自动化分别留痕；每条写清执行者与状态。"
    >
      {vm.executionFeed.length === 0 ? (
        <p className="text-xs text-[var(--muted)]">暂无执行流水。</p>
      ) : (
        <div className="space-y-2">
          {vm.executionFeed.map((log) => (
            <ExecutionLogRow key={log.id} log={log} />
          ))}
        </div>
      )}
    </ManagementPanel>
  );

  const pendingOnly = focus === "pending";

  const mainSections = (
    <>
      <ActionHubProgressRail
        segments={railSegments}
        onNavigate={scrollToSection}
      />
      {section(
        "action-hub-pending",
        "待审批动作",
        "需审批闭环的动作；摘要列表 + 详情抽屉；审批打开右侧面板（原型即时反馈）。",
        vm.pendingApprovals,
      )}
      {section(
        "action-hub-agent",
        "智能体执行监控",
        "智能体模式且处于排队/执行中的动作。",
        vm.agentMonitoring,
      )}
      {section(
        "action-hub-in-progress",
        "执行中动作",
        "口径上包含各执行模式下的「进行中」状态。",
        vm.inProgress,
      )}
      {section(
        "action-hub-high-risk",
        "高风险动作",
        "风险等级为高/极高的动作（可与待审批重叠，便于拦截）。",
        vm.highRisk,
      )}
      {section(
        "action-hub-auto",
        "已自动执行",
        "自动化规则已完成回写的动作。",
        vm.autoExecuted,
      )}
      {section(
        "action-hub-completed",
        "已回写结果",
        "人工或智能体路径上已标记完成的动作（自动化完成见上栏）。",
        vm.completed,
      )}
      {section(
        "action-hub-rolled",
        "已回滚动作",
        "执行状态为已回滚的条目。",
        vm.rolledBack,
      )}

      <ManagementPanel
        id="action-hub-approval-audit"
        title="审计记录 · 审批留痕"
        description="跨项目聚合的审批记录（当前查询下仅为本项目，若有）。"
      >
        {vm.approvalAuditTrail.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无审批记录。</p>
        ) : (
          <ul className="space-y-2 text-xs">
            {vm.approvalAuditTrail.map((r) => (
              <li
                key={r.id}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <span className="text-[var(--foreground)]">
                  {approvalStatusLabel(r.status)}
                </span>
                <span className="mx-2 text-[var(--muted)]">{r.approver}</span>
                <span className="text-[var(--muted)]">动作 {r.actionId}</span>
                {r.reason ? (
                  <p className="mt-1 text-[var(--muted)]">备注：{r.reason}</p>
                ) : null}
                <p className="mt-0.5 text-[10px] text-[var(--muted)]">
                  {new Date(r.updatedAt).toLocaleString("zh-CN")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      {executionPanel}
    </>
  );

  const pendingOnlyBlock = (
    <>
      {section(
        "action-hub-pending",
        "待审批动作",
        pendingOnly && projectMeta
          ? "从商品项目深链进入：仅展示待审批分区。"
          : "仅看待审批：全站或本项目收窄后的待批摘要。",
        vm.pendingApprovals,
      )}
      <p className="text-sm">
        <Link
          href={hubQueryBase}
          className="font-medium text-[var(--accent)] hover:underline"
        >
          查看全部动作分区 →
        </Link>
      </p>
    </>
  );

  return (
    <div className="space-y-8">
      <header className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="app-page-title">动作中心</h1>
            <PulseIndicator tone="live" label="协同执行中" />
          </div>
          <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
            先扫分区与计数，再下钻抽屉看细节；列表默认摘要，减少首屏信息堆叠。人机分层与审批留痕一体可查。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {pendingOnly ? (
            <Link
              href={hubQueryBase}
              className="inline-flex rounded-[var(--radius-md)] border border-[var(--accent)]/35 bg-[var(--accent-muted)] px-4 py-2 text-sm font-semibold text-[var(--accent)] hover:bg-[var(--accent)]/20"
            >
              查看全部分区
            </Link>
          ) : (
            <Link
              href={hubQueryPending}
              className="inline-flex rounded-[var(--radius-md)] bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)] hover:bg-[var(--accent-hover)]"
            >
              仅看待审批
            </Link>
          )}
        </div>
      </header>

      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface-elevated)]/50 p-3 ring-1 ring-white/[0.04]">
        <button
          type="button"
          onClick={() => setLegendOpen((v) => !v)}
          className="flex w-full items-center justify-between text-left text-[11px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
        >
          <span>人机协作分层说明（与风险台、项目详情一致）</span>
          <span aria-hidden>{legendOpen ? "−" : "+"}</span>
        </button>
        {legendOpen ? (
          <div className="mt-3 border-t border-[var(--border)]/60 pt-3">
            <OperatingLayerLegend />
          </div>
        ) : null}
      </div>

      {projectMissing ? (
        <div className="rounded-md border border-orange-500/40 bg-orange-500/5 px-3 py-2 text-sm text-[var(--foreground)]">
          未找到对应商品项目，已显示全站动作。请核对链接中的项目 ID。
        </div>
      ) : null}

      {projectMeta ? (
        <div className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-3 text-sm">
          <p className="font-medium text-[var(--foreground)]">
            当前上下文：项目「{projectMeta.name}」
          </p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            以下列表与执行流水均已按本项目收窄（prototype 深链）。
          </p>
          <div className="mt-2 flex flex-wrap gap-3 text-xs">
            <Link
              href={`/projects/${projectMeta.id}`}
              className="font-medium text-[var(--accent)] hover:underline"
            >
              打开商品项目详情
            </Link>
            <Link href="/action-hub" className="text-[var(--accent)] hover:underline">
              查看全站动作中心
            </Link>
          </div>
        </div>
      ) : null}

      {focus === "execution" && projectMeta ? (
        <div className="space-y-4">
          {executionPanel}
          <p className="text-sm">
            <Link
              href={hubQueryBase}
              className="font-medium text-[var(--accent)] hover:underline"
            >
              查看本项目全部动作分区 →
            </Link>
          </p>
        </div>
      ) : pendingOnly ? (
        pendingOnlyBlock
      ) : (
        mainSections
      )}

      {approvalRow ? (
        <ApprovalDrawer
          row={approvalRow}
          onClose={() => setApprovalRow(null)}
        />
      ) : null}
      {detailRow ? (
        <ActionDetailDrawer
          row={detailRow}
          onClose={() => setDetailRow(null)}
        />
      ) : null}
    </div>
  );
}
