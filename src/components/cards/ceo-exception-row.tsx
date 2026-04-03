import Link from "next/link";
import type { ExceptionItem } from "@/domain/types";
import { riskLevelLabel } from "@/domain/mappers/display-zh";
import { riskSeveritySurfaceClasses } from "@/domain/mappers/visual-surfaces";
import {
  exceptionSourceToLayer,
  OperatingLayerBadge,
} from "@/components/cards/operating-layer-badge";

type CeoExceptionRowProps = {
  exception: ExceptionItem;
  projectName?: string;
};

export function CeoExceptionRow({ exception, projectName }: CeoExceptionRowProps) {
  const sourceLayer = exceptionSourceToLayer(exception.source);
  const showHumanLayer =
    exception.requiresHumanIntervention && sourceLayer !== "human";
  const tone = riskSeveritySurfaceClasses(exception.severity);

  return (
    <div
      className={`rounded-[var(--radius-md)] border px-3 py-2.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)] transition-colors duration-200 hover:border-[var(--accent)]/30 ${tone}`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <OperatingLayerBadge variant={sourceLayer} />
        {showHumanLayer ? <OperatingLayerBadge variant="human" /> : null}
        <span className="font-medium text-[var(--foreground)]">
          风险 {riskLevelLabel(exception.severity)}
        </span>
        {exception.projectId && projectName ? (
          <span className="text-[var(--muted)]">商品项目 · {projectName}</span>
        ) : exception.projectId ? (
          <span className="text-[var(--muted)]">项目 {exception.projectId}</span>
        ) : (
          <span className="text-[var(--muted)]">全局</span>
        )}
      </div>
      <p className="mt-1 text-[var(--foreground)]">{exception.summary}</p>
      {exception.projectId ? (
        <p className="mt-1.5">
          <Link
            href={`/projects/${exception.projectId}`}
            className="text-[var(--accent)] hover:underline"
          >
            进入商品项目详情 →
          </Link>
        </p>
      ) : null}
      {exception.requiresHumanIntervention ? (
        <p className="mt-1.5 text-[var(--accent)]">需人工介入</p>
      ) : null}
    </div>
  );
}
