import Link from "next/link";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import type { ActionHubRow } from "@/domain/types";
import {
  approvalStatusLabel,
  executionStatusLabel,
  riskLevelLabel,
} from "@/domain/mappers/display-zh";
import {
  describeActionProgressLine,
  OperatingLayerBadge,
  triggeredByToLayer,
} from "@/components/cards/operating-layer-badge";

type ActionHubActionRowProps = {
  row: ActionHubRow;
  onOpenApproval?: (row: ActionHubRow) => void;
  onOpenDetail?: (row: ActionHubRow) => void;
  /** compact：摘要一行 + 详情，适合列表首屏扫读 */
  compact?: boolean;
};

export function ActionHubActionRow({
  row,
  onOpenApproval,
  onOpenDetail,
  compact = false,
}: ActionHubActionRowProps) {
  const { action: a, projectId, projectName } = row;
  const showApprovalCTA =
    a.approvalStatus === "pending" && a.requiresHumanApproval;
  const layer = triggeredByToLayer(a.triggeredBy);

  if (compact) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-md)] border border-[var(--border)]/85 bg-[var(--surface-elevated)]/35 px-3 py-2 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
        <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
          <OperatingLayerBadge variant={layer} />
          <span className="min-w-0 truncate font-medium text-[var(--foreground)]">
            {a.title}
          </span>
          <span className="rounded bg-[var(--border)]/25 px-1.5 py-0.5 text-[10px] text-[var(--muted)]">
            {executionStatusLabel(a.executionStatus)} ·{" "}
            {approvalStatusLabel(a.approvalStatus)}
          </span>
          <span className="text-[10px] text-[var(--muted-2)]">
            {LIFECYCLE_STAGE_LABELS[a.sourceStage]} · 风险{" "}
            {riskLevelLabel(a.risk)}
          </span>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5">
          {onOpenDetail ? (
            <button
              type="button"
              onClick={() => onOpenDetail(row)}
              className="rounded-[var(--radius-md)] border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--surface-elevated)]"
            >
              详情
            </button>
          ) : null}
          {showApprovalCTA && onOpenApproval ? (
            <button
              type="button"
              onClick={() => onOpenApproval(row)}
              className="rounded-[var(--radius-md)] bg-[var(--accent)] px-2.5 py-1 text-[11px] font-semibold text-white shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)] transition-colors hover:bg-[var(--accent-hover)]"
            >
              审批
            </button>
          ) : null}
          <Link
            href={`/projects/${projectId}`}
            className="text-[11px] font-medium text-[var(--accent)] hover:underline"
          >
            项目
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)]/85 bg-[var(--surface-elevated)]/35 px-3 py-2.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-colors hover:border-[var(--border)]">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <OperatingLayerBadge variant={layer} />
          <span className="font-medium text-[var(--foreground)]">{a.title}</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {onOpenDetail ? (
            <button
              type="button"
              onClick={() => onOpenDetail(row)}
              className="rounded-[var(--radius-md)] border border-[var(--border)] px-2 py-1 text-[11px] font-medium text-[var(--foreground)] transition-colors hover:bg-[var(--surface-elevated)]"
            >
              详情
            </button>
          ) : null}
          {showApprovalCTA && onOpenApproval ? (
            <button
              type="button"
              onClick={() => onOpenApproval(row)}
              className="rounded-[var(--radius-md)] bg-[var(--accent)] px-2.5 py-1 text-[11px] font-semibold text-white shadow-[inset_0_-1px_0_rgba(0,0,0,0.12)] transition-colors hover:bg-[var(--accent-hover)]"
            >
              审批
            </button>
          ) : null}
        </div>
      </div>
      <p className="mt-1 text-[var(--muted)]">{a.summary}</p>
      <p className="mt-2 text-[10px] leading-relaxed text-[var(--muted)]">
        {describeActionProgressLine(a)}
      </p>
      <div className="mt-2 grid gap-1 text-[10px] text-[var(--muted)] sm:grid-cols-2">
        <p>
          <span className="text-[var(--foreground)]">来源项目</span>：{projectName}{" "}
          <Link
            href={`/projects/${projectId}`}
            className="text-[var(--accent)] hover:underline"
          >
            打开商品项目详情
          </Link>
        </p>
        <p>
          <span className="text-[var(--foreground)]">来源阶段</span>：
          {LIFECYCLE_STAGE_LABELS[a.sourceStage]}
        </p>
        <p className="sm:col-span-2">
          <span className="text-[var(--foreground)]">风险等级</span>：
          {riskLevelLabel(a.risk)}
        </p>
      </div>
    </div>
  );
}
