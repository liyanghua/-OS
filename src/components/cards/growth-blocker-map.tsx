import Link from "next/link";
import type { ExceptionItem, LifecycleStage, ProjectObject } from "@/domain/types";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import { riskLevelLabel } from "@/domain/mappers/display-zh";

const FALLBACK_STAGE: LifecycleStage = "review_capture";

/** 无 projectId 的例外归入复盘沉淀阶段展示（与主线总览一致） */
export function groupBlockersByStage(
  blockers: ExceptionItem[],
  projects: ProjectObject[],
): Record<LifecycleStage, ExceptionItem[]> {
  const stageForException = (ex: ExceptionItem): LifecycleStage => {
    if (!ex.projectId) return FALLBACK_STAGE;
    return projects.find((p) => p.id === ex.projectId)?.stage ?? FALLBACK_STAGE;
  };

  const stages: LifecycleStage[] = [
    "opportunity_pool",
    "new_product_incubation",
    "launch_validation",
    "growth_optimization",
    "legacy_upgrade",
    "review_capture",
  ];
  const init = Object.fromEntries(
    stages.map((s) => [s, [] as ExceptionItem[]]),
  ) as Record<LifecycleStage, ExceptionItem[]>;

  for (const ex of blockers) {
    const st = stageForException(ex);
    init[st].push(ex);
  }
  return init;
}

type GrowthBlockerMapProps = {
  grouped: Record<LifecycleStage, ExceptionItem[]>;
};

export function GrowthBlockerMap({ grouped }: GrowthBlockerMapProps) {
  const stages = Object.entries(grouped).filter(([, list]) => list.length > 0);
  if (stages.length === 0) {
    return (
      <p className="text-xs text-[var(--muted)]">当前无阻塞类例外（原型）。</p>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {stages.map(([stage, list]) => (
        <div
          key={stage}
          className="rounded-md border border-[var(--border)] bg-[var(--surface)] p-3"
        >
          <h4 className="text-xs font-semibold text-[var(--foreground)]">
            {LIFECYCLE_STAGE_LABELS[stage as LifecycleStage]}
          </h4>
          <ul className="mt-2 space-y-2">
            {list.map((ex) => (
              <li key={ex.id} className="text-xs text-[var(--muted)]">
                <span className="text-[var(--foreground)]">
                  {riskLevelLabel(ex.severity)}
                </span>
                ：{ex.summary}
                {ex.projectId ? (
                  <span className="mt-1 block">
                    <Link
                      href={`/projects/${ex.projectId}`}
                      className="text-[var(--accent)] hover:underline"
                    >
                      进入商品项目详情 →
                    </Link>
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
