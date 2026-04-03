import Link from "next/link";
import type { ActionItem } from "@/domain/types";
import {
  approvalStatusLabel,
  riskLevelLabel,
  triggeredByLabel,
} from "@/domain/mappers/display-zh";
import { riskSeveritySurfaceClasses } from "@/domain/mappers/visual-surfaces";

type CeoApprovalRowProps = {
  action: ActionItem;
  projectName: string;
};

export function CeoApprovalRow({ action, projectName }: CeoApprovalRowProps) {
  const tone = riskSeveritySurfaceClasses(action.risk);
  return (
    <div
      className={`rounded-md border px-3 py-2 text-xs transition-colors duration-200 hover:border-[var(--accent)]/25 ${tone}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-[var(--foreground)]">
          {action.title}
        </span>
        <span className="rounded bg-[var(--muted)]/15 px-1.5 py-0.5 text-[var(--muted)]">
          {triggeredByLabel(action.triggeredBy)}
        </span>
        <span className="text-[var(--muted)]">
          {approvalStatusLabel(action.approvalStatus)}
        </span>
        <span className="text-[var(--muted)]">
          风险 {riskLevelLabel(action.risk)}
        </span>
      </div>
      <div className="mt-1 text-[var(--muted)]">
        商品项目 · {projectName}{" "}
        <Link
          href={`/projects/${action.sourceProjectId}`}
          className="text-[var(--accent)] hover:underline"
        >
          进入详情 →
        </Link>
      </div>
      <p className="mt-1 text-[var(--foreground)]">{action.summary}</p>
      {action.requiresHumanApproval ? (
        <p className="mt-1.5 text-[var(--accent)]">需您拍板</p>
      ) : null}
    </div>
  );
}
