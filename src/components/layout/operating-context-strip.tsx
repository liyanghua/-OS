"use client";

import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import { useAppStore } from "@/state/app-store";
import { ROLE_LABELS } from "@/state/mock-projects";

export function OperatingContextStrip() {
  const { roleView, projects } = useAppStore();
  const top = projects[0];

  return (
    <div className="border-b border-[var(--border)] bg-[var(--strip-bg)] px-6 py-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="text-[11px] leading-relaxed tracking-tight text-[var(--muted)]">
        <span className="font-medium text-[var(--foreground)]">
          {ROLE_LABELS[roleView]}
        </span>
        {top ? (
          <>
            {" · "}
            <span className="text-[var(--foreground)]">{top.name}</span>
            {" · 阶段："}
            <span className="font-medium text-[var(--accent)]">
              {LIFECYCLE_STAGE_LABELS[top.stage]}
            </span>
            {top.latestPulse ? (
              <>
                {" · 经营脉冲："}
                <span className="text-[var(--foreground)]">{top.latestPulse}</span>
              </>
            ) : null}
          </>
        ) : null}
      </p>
    </div>
  );
}
