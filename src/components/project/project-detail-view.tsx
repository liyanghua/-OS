"use client";

import Link from "next/link";
import { useState } from "react";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import type {
  ActionHubRow,
  ActionItem,
  DecisionOption,
  ProjectObject,
  ProjectObjectPageVM,
} from "@/domain/types";
import {
  agentStatusLabel,
  approvalStatusLabel,
  assetTypeLabel,
  confidenceLevelPercentLabel,
  creativeVersionStatusLabel,
  expressionReadinessLabel,
  personRoleLabel,
  projectHealthLabel,
  projectTypeLabel,
  reviewVerdictLabel,
  riskLevelLabel,
  samplingStatusLabel,
} from "@/domain/mappers/display-zh";
import { ManagementPanel } from "@/components/cards/management-panel";
import {
  OperatingLayerBadge,
  OperatingLayerLegend,
} from "@/components/cards/operating-layer-badge";
import { ActionHubActionRow } from "@/components/governance/action-hub-action-row";
import { ActionDetailDrawer } from "@/components/governance/action-detail-drawer";
import { ApprovalDrawer } from "@/components/governance/approval-drawer";
import { ExecutionLogRow } from "@/components/governance/execution-log-row";
import { StageProgressRail } from "@/components/cards/stage-progress-rail";
import { AiSignalFrame } from "@/components/cards/ai-signal-frame";
import { AgentStatusIndicator } from "@/components/ui/agent-status-indicator";
import type { EvidenceRef } from "@/domain/types/evidence";

type ProjectDetailViewProps = {
  vm: ProjectObjectPageVM;
};

function toHubRow(p: ProjectObject, a: ActionItem): ActionHubRow {
  return { action: a, projectId: p.id, projectName: p.name };
}

function OptionCompareCard({
  opt,
  variant,
}: {
  opt: DecisionOption;
  variant: "recommended" | "alternate";
}) {
  const isRec = variant === "recommended";
  return (
    <div
      className={`rounded-md border px-3 py-3 text-xs ${
        isRec
          ? "border-[var(--accent)]/55 bg-[var(--accent)]/8"
          : "border-[var(--border)] bg-[var(--surface-elevated)]/30"
      }`}
    >
      <p className="text-[10px] font-semibold uppercase tracking-wide text-[var(--muted)]">
        {isRec ? "推荐方案" : "对比方案"}
      </p>
      <p className="mt-2 font-medium text-[var(--foreground)]">{opt.title}</p>
      <p className="mt-1 text-[var(--muted)]">{opt.summary}</p>
      <dl className="mt-2 space-y-1 text-[10px] text-[var(--muted)]">
        <div className="flex gap-2">
          <dt>风险</dt>
          <dd className="text-[var(--foreground)]">{riskLevelLabel(opt.risk)}</dd>
        </div>
        <div className="flex gap-2">
          <dt>预期收益</dt>
          <dd className="text-[var(--foreground)]">{opt.expectedImpact}</dd>
        </div>
        <div className="flex flex-wrap gap-2">
          <dt>资源</dt>
          <dd>{opt.resourcesNeeded}</dd>
        </div>
        <div className="flex flex-wrap gap-2">
          <dt>验证窗口</dt>
          <dd>{opt.validationWindow}</dd>
        </div>
      </dl>
    </div>
  );
}

function evidenceRefTypeLabel(t: EvidenceRef["type"]): string {
  const m: Record<EvidenceRef["type"], string> = {
    metric: "指标",
    history: "历史",
    case: "案例",
    rule: "规则",
    agent_observation: "智能体观察",
    user_feedback: "用户反馈",
    competitive_scan: "竞品扫描",
  };
  return m[t];
}

export function ProjectDetailView({ vm }: ProjectDetailViewProps) {
  const [detailRow, setDetailRow] = useState<ActionHubRow | null>(null);
  const [approvalRow, setApprovalRow] = useState<ActionHubRow | null>(null);
  const [collabLegendOpen, setCollabLegendOpen] = useState(false);

  const { project: p, realtime, recentFeed, nextDecisionHint } = vm;
  const pulse = p.latestPulse ?? realtime?.latestPulse;

  const suggestedActions = p.actions.filter(
    (a) => a.triggeredBy === "decision_brain",
  );
  const pendingActions = p.actions.filter((a) => a.approvalStatus === "pending");
  const inFlightActions = p.actions.filter(
    (a) =>
      a.executionStatus === "in_progress" || a.executionStatus === "queued",
  );
  const writebackActions = p.actions.filter(
    (a) =>
      a.executionStatus === "completed" && a.executionMode !== "automation",
  );
  const rolledBackActions = p.actions.filter(
    (a) => a.executionStatus === "rolled_back",
  );
  const autoDoneActions = p.actions.filter(
    (a) =>
      a.executionMode === "automation" && a.executionStatus === "completed",
  );

  const pendingApprovers = (p.approvals ?? []).filter(
    (r) => r.status === "pending",
  );
  const biggestProblem =
    p.keyBlocker ??
    p.decisionObject?.problemOrOpportunity ??
    pulse ??
    (p.health !== "healthy"
      ? `健康度 ${projectHealthLabel(p.health)}、风险 ${riskLevelLabel(p.riskLevel)}，需持续关注`
      : null) ??
    "暂无单列「最大问题」，可补充关键阻塞或经营脉冲";

  const recommendedActionTitle =
    suggestedActions[0]?.title ??
    pendingActions[0]?.title ??
    "暂无待列出的建议/待批动作";

  const stakeholderLine =
    p.stakeholders.length > 0
      ? p.stakeholders
          .map((s) => `${s.name}（${personRoleLabel(s.role)}）`)
          .join("、")
      : "尚未配置干系人";

  const approverLine =
    pendingApprovers.length > 0
      ? `审批待办指向：${pendingApprovers.map((r) => r.approver).join("、")}`
      : null;

  const humanNodeSummary = [approverLine, `干系人：${stakeholderLine}`, `下一决策焦点：${nextDecisionHint}`]
    .filter(Boolean)
    .join("；");

  const primaryActionHref =
    pendingActions.length > 0
      ? `/action-hub?projectId=${encodeURIComponent(p.id)}&focus=pending`
      : `/action-hub?projectId=${encodeURIComponent(p.id)}`;
  const primaryActionLabel =
    pendingActions.length > 0 ? "收口待审批动作" : "查看与推进本项目动作";

  return (
    <div className="space-y-6">
      <nav className="text-xs text-[var(--muted)]">
        <Link href="/projects" className="text-[var(--accent)] hover:underline">
          商品项目
        </Link>
        <span className="mx-2">/</span>
        <span className="text-[var(--foreground)]">{p.name}</span>
      </nav>

      <section
        className="rounded-[var(--radius-lg)] border-2 border-[var(--accent)]/30 bg-[var(--surface)] p-5 shadow-[var(--shadow-card)] ring-1 ring-[var(--accent)]/15"
        style={{ boxShadow: "var(--shadow-card)" }}
      >
        <h2 className="text-lg font-semibold tracking-tight text-[var(--foreground)] md:text-xl">
          决策焦点
        </h2>
        <p className="mt-1.5 max-w-3xl text-sm text-[var(--muted)]">
          先脉冲与阶段位置，再最大张力与推荐动作；本块为页面视觉中心（原则：先脉冲后分析）。
        </p>
        <div className="mt-4">
          <StageProgressRail current={p.stage} />
        </div>
        {pulse ? (
          <div className="mt-4">
            <AiSignalFrame label="经营大脑 · 最新脉冲">
              {pulse}
            </AiSignalFrame>
          </div>
        ) : null}
        <div className="mt-4 space-y-2 text-sm">
          <p>
            <span className="text-xs text-[var(--muted)]">当前最大问题</span>
            <span className="mt-1 block text-[var(--foreground)]">{biggestProblem}</span>
          </p>
          <p>
            <span className="text-xs text-[var(--muted)]">当前推荐动作</span>
            <span className="mt-1 block font-medium text-[var(--foreground)]">
              {recommendedActionTitle}
            </span>
          </p>
          {p.decisionObject ? (
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="text-[var(--muted)]">经营大脑置信度</span>
              <span
                className={`rounded-md border px-2.5 py-1 font-semibold tabular-nums ${
                  p.decisionObject.confidence === "high"
                    ? "border-sky-400/45 bg-sky-500/15 text-sky-100"
                    : p.decisionObject.confidence === "low"
                      ? "border-amber-400/45 bg-amber-500/12 text-amber-100"
                      : "border-[var(--border)] bg-[var(--surface-elevated)]/50 text-[var(--foreground)]/90"
                }`}
              >
                AI 置信度 {confidenceLevelPercentLabel(p.decisionObject.confidence)}
                <span className="ml-1 text-[11px] font-normal opacity-90">
                  · 结构化建议
                </span>
              </span>
              {p.decisionObject.requiresHumanApproval ? (
                <span className="text-amber-200/95">· 需人工拍板后可执行</span>
              ) : null}
            </div>
          ) : null}
          <p className="text-xs text-[var(--muted)]">{humanNodeSummary}</p>
        </div>
        <div className="mt-5 flex flex-wrap gap-2">
          <Link
            href={primaryActionHref}
            className="inline-flex rounded-[var(--radius-md)] bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-[var(--accent-foreground)] shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)] transition-colors hover:bg-[var(--accent-hover)]"
          >
            {primaryActionLabel}
          </Link>
          <Link
            href={`/lifecycle/review-capture?projectId=${encodeURIComponent(p.id)}`}
            className="inline-flex rounded-[var(--radius-md)] border border-[var(--border)] px-4 py-2.5 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--surface-elevated)]"
          >
            复盘与资产沉淀
          </Link>
        </div>
      </section>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-[var(--border)]/50 pb-3 text-xs text-[var(--accent)]">
        <span className="text-[var(--muted)]">主线联动</span>
        <Link
          href={`/action-hub?projectId=${encodeURIComponent(p.id)}`}
          className="font-medium hover:underline"
        >
          全部动作
        </Link>
        <Link
          href={`/action-hub?projectId=${encodeURIComponent(p.id)}&focus=pending`}
          className="hover:underline"
        >
          待审批
        </Link>
        <Link
          href={`/action-hub?projectId=${encodeURIComponent(p.id)}&focus=execution`}
          className="hover:underline"
        >
          执行动态
        </Link>
        <Link
          href={`/lifecycle/review-capture?projectId=${encodeURIComponent(p.id)}`}
          className="hover:underline"
        >
          复盘台
        </Link>
      </div>


      <ManagementPanel
        title="项目协作摘要"
        description="分析向补充字段；决策焦点已在首屏。"
      >
        <div className="space-y-3 text-sm text-[var(--foreground)]">
          <p className="text-lg font-semibold">{p.name}</p>
          <p className="text-[var(--muted)]">{p.statusSummary}</p>
          <dl className="grid gap-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
            <div>
              <dt className="text-[var(--muted)]">项目类型</dt>
              <dd className="mt-0.5">{projectTypeLabel(p.type)}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">当前生命周期阶段</dt>
              <dd className="mt-0.5">{LIFECYCLE_STAGE_LABELS[p.stage]}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">当前目标</dt>
              <dd className="mt-0.5">{p.targetSummary}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">项目健康度</dt>
              <dd className="mt-0.5">{projectHealthLabel(p.health)}</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">风险等级</dt>
              <dd className="mt-0.5">{riskLevelLabel(p.riskLevel)}</dd>
            </div>
            <div className="sm:col-span-2 lg:col-span-3">
              <dt className="text-[var(--muted)]">下一关键决策点</dt>
              <dd className="mt-0.5 font-medium text-[var(--accent)]">
                {nextDecisionHint}
              </dd>
            </div>
          </dl>
          {p.keyBlocker ? (
            <p className="rounded-md bg-[#2a1f18] px-2 py-1.5 text-xs text-[#f7936f]">
              当前阻塞：{p.keyBlocker}
            </p>
          ) : (
            <p className="text-xs text-[var(--muted)]">当前无单列阻塞字段。</p>
          )}
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="协同状态条"
        description="人为发起 × 经营建议 × 智能体 × 自动化；图例默认收纳，避免与决策焦点抢视觉。"
      >
        <div className="mb-4">
          <button
            type="button"
            onClick={() => setCollabLegendOpen((v) => !v)}
            className="text-[11px] font-medium text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            {collabLegendOpen ? "收起分层图例" : "展开分层图例"}
          </button>
          {collabLegendOpen ? (
            <div className="mt-3">
              <OperatingLayerLegend />
            </div>
          ) : null}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-md border border-[var(--border)]/60 p-3">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[var(--foreground)] md:text-base">
              经营建议
              <OperatingLayerBadge variant="decision_brain" />
            </h3>
            {p.decisionObject ? (
              <div className="mt-2 space-y-2 text-xs text-[var(--muted)]">
                <p>
                  <span className="text-[var(--foreground)]">建议摘要：</span>
                  {p.decisionObject.rationale}
                </p>
                <p>
                  AI 置信度：
                  <span className="font-medium tabular-nums text-[var(--foreground)]">
                    {confidenceLevelPercentLabel(p.decisionObject.confidence)}
                  </span>
                </p>
                <div>
                  <p className="text-[var(--foreground)]">证据入口</p>
                  {p.decisionObject.evidencePack.refs.length > 0 ? (
                    <ul className="mt-1 max-h-28 space-y-1 overflow-y-auto">
                      {p.decisionObject.evidencePack.refs.map((ref) => (
                        <li key={ref.id} className="rounded bg-[var(--border)]/15 px-2 py-1">
                          <span className="text-[10px] text-[var(--muted)]">
                            {evidenceRefTypeLabel(ref.type)}
                          </span>
                          <span className="mx-1 text-[var(--foreground)]">
                            {ref.summary}
                          </span>
                          {ref.sourceLabel ? (
                            <span className="text-[10px]">（{ref.sourceLabel}）</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-1 text-[10px]">暂无结构化证据引用。</p>
                  )}
                  {p.decisionObject.evidencePack.summary ? (
                    <p className="mt-2 text-[10px]">
                      证据包摘要：{p.decisionObject.evidencePack.summary}
                    </p>
                  ) : null}
                </div>
              </div>
            ) : (
              <p className="mt-2 text-xs text-[var(--muted)]">
                暂无结构化决策对象；可关注下方脉冲与动作建议。
              </p>
            )}
          </div>

          <div className="rounded-md border border-[var(--border)]/60 p-3">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[var(--foreground)] md:text-base">
              智能体
              <OperatingLayerBadge variant="scenario_agent" />
            </h3>
            {p.agentStates.length > 0 ? (
              <ul className="mt-2 space-y-2 text-sm">
                {p.agentStates.map((g) => (
                  <li
                    key={g.id}
                    className="rounded border border-[var(--border)]/50 px-2.5 py-2"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <AgentStatusIndicator status={g.status} />
                      <span className="font-semibold text-[var(--foreground)]">
                        {agentStatusLabel(g.status)}
                      </span>
                    </div>
                    <p className="mt-1 text-[var(--muted)]">{g.summary}</p>
                    {g.waitingReason ? (
                      <p className="mt-0.5 text-[10px] text-[var(--muted)]">
                        等待原因：{g.waitingReason}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-[var(--muted)]">
                暂无场景智能体状态行。
              </p>
            )}
          </div>

          <div className="rounded-md border border-[var(--border)]/60 p-3">
            <h3 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-[var(--foreground)] md:text-base">
              执行端
              <OperatingLayerBadge variant="automation" />
            </h3>
            <ul className="mt-2 space-y-1 text-xs text-[var(--muted)]">
              <li>
                自动执行端已完成：{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {autoDoneActions.length}
                </span>{" "}
                件
              </li>
              <li>
                待审批：{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {pendingActions.length}
                </span>{" "}
                件
              </li>
              <li>
                人工或场景 Agent 已回写（非自动化完成）：{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {writebackActions.length}
                </span>{" "}
                件
              </li>
              <li>
                已回滚：{" "}
                <span className="font-medium text-[var(--foreground)]">
                  {rolledBackActions.length}
                </span>{" "}
                件
              </li>
            </ul>
          </div>

          <div className="rounded-md border border-[var(--border)]/60 p-3">
            <h3 className="flex flex-wrap items-center gap-2 text-xs font-semibold text-[var(--foreground)]">
              人为发起
              <OperatingLayerBadge variant="human" />
            </h3>
            <p className="mt-2 text-xs text-[var(--muted)]">
              待批动作：{" "}
              <span className="text-[var(--foreground)]">
                {pendingActions.length}
              </span>{" "}
              件。责任人（owner 字段）与各干系人需协同拍板。
            </p>
            {p.stakeholders.length > 0 ? (
              <ul className="mt-2 list-inside list-disc text-xs text-[var(--foreground)]">
                {p.stakeholders.map((s) => (
                  <li key={s.id}>
                    {s.name}（{personRoleLabel(s.role)}）
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-xs text-[var(--muted)]">暂无干系人列表。</p>
            )}
            {pendingApprovers.length > 0 ? (
              <p className="mt-2 text-xs text-[var(--muted)]">
                审批记录中的待办审批人：
                {pendingApprovers.map((r) => r.approver).join("、")}
              </p>
            ) : pendingActions.length > 0 ? (
              <p className="mt-2 text-xs text-[var(--muted)]">
                尚无与待批动作关联的待处理审批记录（mock 可补全）。
              </p>
            ) : null}
          </div>
        </div>
      </ManagementPanel>

      <ManagementPanel
        title="决策对象"
        description="当前问题或机会、原因判断、候选方案与推荐；风险与预期收益并列可见。"
      >
        {p.decisionObject ? (
          <div className="space-y-4 text-sm">
            <div>
              <p className="text-[10px] font-medium uppercase text-[var(--muted)]">
                当前问题 / 机会
              </p>
              <p className="mt-1 font-medium text-[var(--foreground)]">
                {p.decisionObject.problemOrOpportunity}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase text-[var(--muted)]">
                原因判断
              </p>
              <p className="mt-1 text-[var(--muted)]">
                {p.decisionObject.rootCauseSummary ?? p.decisionObject.rationale}
              </p>
            </div>
            <div>
              <p className="text-[10px] font-medium uppercase text-[var(--muted)]">
                候选方案（对比布局）
              </p>
              {(() => {
                const opts = p.decisionObject!.options;
                const recId = p.decisionObject!.recommendedOptionId;
                const primary =
                  opts.find((o) => o.id === recId) ?? opts[0] ?? null;
                const secondary = primary
                  ? opts.find((o) => o.id !== primary.id) ?? null
                  : null;
                const rest =
                  primary && secondary
                    ? opts.filter(
                        (o) => o.id !== primary.id && o.id !== secondary.id,
                      )
                    : [];

                if (!primary) {
                  return (
                    <p className="mt-2 text-xs text-[var(--muted)]">暂无方案条目。</p>
                  );
                }
                return (
                  <div className="mt-2 space-y-3">
                    {secondary ? (
                      <div className="grid gap-3 md:grid-cols-2">
                        <OptionCompareCard opt={primary} variant="recommended" />
                        <OptionCompareCard opt={secondary} variant="alternate" />
                      </div>
                    ) : (
                      <OptionCompareCard opt={primary} variant="recommended" />
                    )}
                    {rest.length > 0 ? (
                      <div>
                        <p className="text-[10px] text-[var(--muted)]">
                          其他备选（{rest.length}）
                        </p>
                        <ul className="mt-1 space-y-2 text-xs">
                          {rest.map((opt) => (
                            <li
                              key={opt.id}
                              className="rounded border border-[var(--border)]/70 px-2 py-1.5 text-[var(--muted)]"
                            >
                              <span className="font-medium text-[var(--foreground)]">
                                方案 {String.fromCharCode(65 + opts.indexOf(opt))}
                              </span>
                              {" · "}
                              {opt.title}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                );
              })()}
            </div>
            <div className="flex flex-wrap gap-4 text-xs">
              <p>
                推荐方案 ID：
                <code className="rounded bg-[var(--border)]/30 px-1">
                  {p.decisionObject.recommendedOptionId ?? "未指定"}
                </code>
              </p>
              <p>
                是否需要人工审批：
                <span className="font-medium text-[var(--foreground)]">
                  {p.decisionObject.requiresHumanApproval ? "是" : "否"}
                </span>
              </p>
            </div>
            {p.decisionObject.pendingQuestions &&
            p.decisionObject.pendingQuestions.length > 0 ? (
              <div>
                <p className="text-[10px] font-medium text-[var(--muted)]">
                  待澄清问题
                </p>
                <ul className="mt-1 list-inside list-disc text-xs text-[var(--muted)]">
                  {p.decisionObject.pendingQuestions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">暂无决策对象</p>
        )}
      </ManagementPanel>

      <ManagementPanel title="商品定义" description="定位、人群与打样等（如有）。">
        {p.definition ? (
          <dl className="grid gap-2 text-sm text-[var(--foreground)]">
            <div>
              <dt className="text-xs text-[var(--muted)]">定位</dt>
              <dd>{p.definition.positioning}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--muted)]">人群</dt>
              <dd>{p.definition.targetAudience}</dd>
            </div>
            <div>
              <dt className="text-xs text-[var(--muted)]">打样状态</dt>
              <dd>{samplingStatusLabel(p.definition.samplingStatus)}</dd>
            </div>
          </dl>
        ) : (
          <p className="text-sm text-[var(--muted)]">暂无商品定义</p>
        )}
      </ManagementPanel>

      <ManagementPanel title="表达规划" description="内容与视觉说明、版本列表（如有）。">
        {p.expression ? (
          <div className="space-y-2 text-sm text-[var(--foreground)]">
            <p>
              <span className="text-[var(--muted)]">就绪状态：</span>
              {expressionReadinessLabel(p.expression.readinessStatus)}
            </p>
            {p.expression.creativeVersions.length > 0 ? (
              <ul className="list-inside list-disc text-[var(--muted)]">
                {p.expression.creativeVersions.map((c) => (
                  <li key={c.id}>
                    {c.name}（{creativeVersionStatusLabel(c.status)}）
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[var(--muted)]">暂无创意版本记录</p>
            )}
          </div>
        ) : (
          <p className="text-sm text-[var(--muted)]">暂无表达规划</p>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="经营闭环"
        description="从经营大脑建议动作到审批、执行与回写；复盘与资产候选同一屏收口；审计记录可追溯到动作。"
      >
        {([
          ["当前建议动作", suggestedActions],
          ["待批动作", pendingActions],
          ["执行中动作", inFlightActions],
          ["已自动执行", autoDoneActions],
          ["已回写结果", writebackActions],
          ["已回滚动作", rolledBackActions],
        ] as const).map(([label, list]) => (
          <div key={label} className="mb-4 last:mb-0">
            <p className="text-xs font-semibold text-[var(--foreground)]">
              {label}
              <span className="ml-2 font-normal text-[var(--muted)]">
                ({list.length})
              </span>
            </p>
            {list.length === 0 ? (
              <p className="mt-1 text-xs text-[var(--muted)]">暂无。</p>
            ) : (
              <div className="mt-2 space-y-2">
                {list.map((a) => (
                  <ActionHubActionRow
                    key={a.id}
                    row={toHubRow(p, a)}
                    compact
                    onOpenDetail={setDetailRow}
                    onOpenApproval={setApprovalRow}
                  />
                ))}
              </div>
            )}
          </div>
        ))}

        <div className="mt-4 border-t border-[var(--border)]/60 pt-4">
          <p className="text-xs font-semibold text-[var(--foreground)]">
            当前复盘摘要
          </p>
          {p.review ? (
            <div className="mt-2 text-sm text-[var(--foreground)]">
              <p className="font-medium">
                复盘结论：{reviewVerdictLabel(p.review.verdict)}
              </p>
              <p className="mt-1 text-[var(--muted)]">{p.review.resultSummary}</p>
            </div>
          ) : (
            <p className="mt-1 text-xs text-[var(--muted)]">暂无复盘摘要</p>
          )}
        </div>

        <div className="mt-4 border-t border-[var(--border)]/60 pt-4">
          <p className="text-xs font-semibold text-[var(--foreground)]">
            待沉淀资产候选
          </p>
          {p.assetCandidates && p.assetCandidates.length > 0 ? (
            <ul className="mt-2 space-y-2 text-xs">
              {p.assetCandidates.map((c) => (
                <li
                  key={c.id}
                  className="rounded-md border border-dashed border-[var(--border)] px-2 py-1.5"
                >
                  <span className="font-medium text-[var(--foreground)]">
                    {c.title}
                  </span>
                  <span className="ml-2 text-[10px] text-[var(--muted)]">
                    {assetTypeLabel(c.type)}
                  </span>
                  <span className="ml-2 text-[10px]">
                    {approvalStatusLabel(c.approvalStatus)}
                  </span>
                  <p className="mt-1 text-[var(--muted)]">{c.rationale}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-xs text-[var(--muted)]">暂无候选。</p>
          )}
        </div>

        <div className="mt-4 border-t border-[var(--border)]/60 pt-4">
          <p className="text-xs font-semibold text-[var(--foreground)]">
            审计记录
          </p>
          <p className="mt-1 text-[10px] text-[var(--muted)]">
            来自 ExecutionLog：执行者类型、状态与时间戳。
          </p>
          {p.executionLogs && p.executionLogs.length > 0 ? (
            <div className="mt-2 space-y-2">
              {[...p.executionLogs]
                .sort(
                  (x, y) =>
                    new Date(y.updatedAt).getTime() -
                    new Date(x.updatedAt).getTime(),
                )
                .map((log) => (
                  <ExecutionLogRow key={log.id} log={log} />
                ))}
            </div>
          ) : (
            <p className="mt-2 text-xs text-[var(--muted)]">暂无执行审计。</p>
          )}
        </div>

        {recentFeed && recentFeed.length > 0 ? (
          <div className="mt-4 border-t border-[var(--border)]/60 pt-4">
            <p className="text-xs font-semibold text-[var(--foreground)]">
              最近动态（推导）
            </p>
            <ul className="mt-2 list-inside list-disc text-xs text-[var(--muted)]">
              {recentFeed.map((f) => (
                <li key={f.id}>{f.summary}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </ManagementPanel>

      {detailRow ? (
        <ActionDetailDrawer
          row={detailRow}
          onClose={() => setDetailRow(null)}
        />
      ) : null}
      {approvalRow ? (
        <ApprovalDrawer
          row={approvalRow}
          onClose={() => setApprovalRow(null)}
        />
      ) : null}
    </div>
  );
}
