"use client";

import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import type { LifecycleStage } from "@/domain/types";

const ORDER: LifecycleStage[] = [
  "opportunity_pool",
  "new_product_incubation",
  "launch_validation",
  "growth_optimization",
  "legacy_upgrade",
  "review_capture",
];

type StageProgressRailProps = {
  current: LifecycleStage;
};

/** 生命周期 Progress rail（原则 7：状态条/时间线轻量表达） */
export function StageProgressRail({ current }: StageProgressRailProps) {
  const idx = ORDER.indexOf(current);
  return (
    <nav aria-label="生命周期阶段进度" className="overflow-x-auto pb-1">
      <ol className="flex min-w-max items-stretch gap-1">
        {ORDER.map((stage, i) => {
          const past = idx >= 0 && i < idx;
          const here = i === idx;
          const future = idx >= 0 && i > idx;
          return (
            <li key={stage} className="flex items-center">
              {i > 0 ? (
                <span
                  aria-hidden
                  className={`mx-0.5 h-px w-4 shrink-0 sm:w-5 ${
                    past || here ? "bg-[var(--accent)]/45" : "bg-[var(--border)]"
                  }`}
                />
              ) : null}
              <span
                className={`rounded-md px-2 py-1 text-[10px] font-semibold whitespace-nowrap sm:text-[11px] ${
                  here
                    ? "bg-[var(--accent-muted)] text-[var(--accent)] ring-1 ring-[var(--accent)]/40"
                    : past
                      ? "bg-[var(--surface-elevated)] text-[var(--foreground)]/75"
                      : future
                        ? "text-[var(--muted-2)]"
                        : "text-[var(--muted)]"
                }`}
              >
                {LIFECYCLE_STAGE_LABELS[stage]}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
