"use client";

import { useState } from "react";
import type { ActionHubRow } from "@/domain/types";
import {
  approvalStatusLabel,
  executionModeLabel,
  executionStatusLabel,
  riskLevelLabel,
  triggeredByLabel,
} from "@/domain/mappers/display-zh";
import { DrawerShell } from "@/components/shell/drawer-shell";

type ApprovalDrawerProps = {
  row: ActionHubRow | null;
  onClose: () => void;
};

export function ApprovalDrawer({ row, onClose }: ApprovalDrawerProps) {
  const [feedback, setFeedback] = useState<string | null>(null);

  if (!row) return null;
  const a = row.action;

  const flash = (text: string) => {
    setFeedback(text);
    window.setTimeout(() => setFeedback(null), 3200);
  };

  const footer = (
    <>
      <div aria-live="polite" className="mb-3 min-h-[1rem] text-xs text-[var(--accent)]">
        {feedback}
      </div>
      <p className="mb-3 text-xs text-[var(--muted)]">
        原型演示：下列操作仅即时反馈文案，不产生真实审批状态。
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          className="flex-1 rounded-[var(--radius-md)] border border-[var(--border)] py-2 text-xs font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--surface-elevated)]"
          onClick={() => flash("已记录驳回意向（原型，未落库）")}
        >
          驳回
        </button>
        <button
          type="button"
          className="flex-1 rounded-[var(--radius-md)] bg-[var(--accent)] py-2 text-xs font-semibold text-white shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)] transition-colors hover:bg-[var(--accent-hover)]"
          onClick={() => flash("已记录同意（原型，未落库）")}
        >
          同意
        </button>
      </div>
    </>
  );

  return (
    <DrawerShell
      onClose={onClose}
      title="审批"
      description="区分经营建议与落地动作；正式驳回/放行待接治理与审计后端。"
      footer={footer}
    >
      <div>
        <p className="text-xs text-[var(--muted)]">动作</p>
        <p className="font-medium text-[var(--foreground)]">{a.title}</p>
      </div>
      <p className="text-[var(--muted)]">{a.summary}</p>
      <dl className="grid gap-2 text-xs">
        <div>
          <dt className="text-[var(--muted)]">来源</dt>
          <dd>{triggeredByLabel(a.triggeredBy)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">执行模式</dt>
          <dd>{executionModeLabel(a.executionMode)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">执行状态</dt>
          <dd>{executionStatusLabel(a.executionStatus)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">审批状态</dt>
          <dd>{approvalStatusLabel(a.approvalStatus)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">风险</dt>
          <dd>{riskLevelLabel(a.risk)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">商品项目</dt>
          <dd>{row.projectName}</dd>
        </div>
      </dl>
    </DrawerShell>
  );
}
