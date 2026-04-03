"use client";

export type ActionHubRailSegment = {
  id: string;
  label: string;
  count: number;
};

type ActionHubProgressRailProps = {
  segments: ActionHubRailSegment[];
  onNavigate: (sectionId: string) => void;
};

/** 动作中心分区导航 rail：点击滚动到对应 ManagementPanel（原则 7） */
export function ActionHubProgressRail({
  segments,
  onNavigate,
}: ActionHubProgressRailProps) {
  return (
    <div
      className="flex flex-wrap gap-2 rounded-[var(--radius-md)] border border-[var(--border-subtle)] bg-[var(--surface-elevated)]/40 p-2"
      role="navigation"
      aria-label="动作分区快速定位"
    >
      {segments.map((s) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onNavigate(s.id)}
          className="rounded-[var(--radius-md)] border border-transparent px-2.5 py-1.5 text-left text-[11px] font-medium text-[var(--foreground)] transition-colors hover:border-[var(--accent)]/35 hover:bg-[var(--accent-muted)]"
        >
          <span>{s.label}</span>
          <span className="ml-1 tabular-nums text-[var(--muted)]">({s.count})</span>
        </button>
      ))}
    </div>
  );
}
