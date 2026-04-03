"use client";

import Link from "next/link";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import type { ActionHubRow } from "@/domain/types";
import {
  approvalStatusLabel,
  executionModeLabel,
  executionStatusLabel,
  riskLevelLabel,
  triggeredByLabel,
} from "@/domain/mappers/display-zh";
import {
  describeActionProgressLine,
  OperatingLayerBadge,
  triggeredByToLayer,
} from "@/components/cards/operating-layer-badge";
import { DrawerShell } from "@/components/shell/drawer-shell";

type ActionDetailDrawerProps = {
  row: ActionHubRow | null;
  onClose: () => void;
};

export function ActionDetailDrawer({ row, onClose }: ActionDetailDrawerProps) {
  if (!row) return null;
  const a = row.action;
  const layer = triggeredByToLayer(a.triggeredBy);

  return (
    <DrawerShell
      onClose={onClose}
      title="动作详情"
      description="完整语境在下；高频入口可在此直接跳转，无需回到全表翻找。"
      maxWidthClass="max-w-lg"
    >
      <div className="flex flex-wrap items-center gap-2">
        <OperatingLayerBadge variant={layer} />
        <span className="text-xs text-[var(--muted)]">
          {approvalStatusLabel(a.approvalStatus)} ·{" "}
          {executionStatusLabel(a.executionStatus)}
        </span>
      </div>
      <div>
        <p className="text-xs text-[var(--muted)]">动作标题</p>
        <p className="font-medium text-[var(--foreground)]">{a.title}</p>
      </div>
      <p className="text-[var(--muted)]">{a.summary}</p>
      <p className="text-xs leading-relaxed text-[var(--foreground)]/90">
        {describeActionProgressLine(a)}
      </p>
      <dl className="grid gap-2 border-t border-[var(--border)]/60 pt-3 text-xs">
        <div>
          <dt className="text-[var(--muted)]">建议来源</dt>
          <dd>{triggeredByLabel(a.triggeredBy)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">执行模式</dt>
          <dd>{executionModeLabel(a.executionMode)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">风险</dt>
          <dd>{riskLevelLabel(a.risk)}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">来源阶段</dt>
          <dd>{LIFECYCLE_STAGE_LABELS[a.sourceStage]}</dd>
        </div>
        <div>
          <dt className="text-[var(--muted)]">商品项目</dt>
          <dd>
            <Link
              href={`/projects/${row.projectId}`}
              className="text-[var(--accent)] hover:underline"
            >
              {row.projectName}
            </Link>
          </dd>
        </div>
      </dl>
      <p className="text-[10px] text-[var(--muted)]">
        <Link
          href={`/action-hub?projectId=${encodeURIComponent(row.projectId)}`}
          className="text-[var(--accent)] hover:underline"
        >
          在本项目动作中心继续查看分区 →
        </Link>
      </p>
    </DrawerShell>
  );
}
