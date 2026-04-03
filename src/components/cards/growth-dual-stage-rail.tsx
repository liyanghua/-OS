/** 增长工作台：首发验证 vs 增长优化 两步轻量状态条（纯展示） */
export function GrowthDualStageRail({
  launchCount,
  growthCount,
}: {
  launchCount: number;
  growthCount: number;
}) {
  const launchOn = launchCount > 0;
  const growthOn = growthCount > 0;

  return (
    <div
      role="presentation"
      className="mb-4 flex flex-col gap-2 rounded-lg border border-[var(--border)]/70 bg-[var(--surface-elevated)]/40 px-3 py-2 text-xs"
    >
      <span className="font-semibold text-[var(--foreground)]">战线节奏</span>
      <div
        className="flex flex-wrap gap-2"
        aria-label="首发验证与增长优化两步"
      >
        <span
          className={`rounded-full px-2.5 py-1 font-medium ${
            launchOn
              ? "bg-[var(--accent)]/20 text-[var(--foreground)] ring-1 ring-[var(--accent)]/35"
              : "bg-[var(--border)]/20 text-[var(--muted)]"
          }`}
        >
          首发验证 · 在盘 {launchCount}
        </span>
        <span
          className={`rounded-full px-2.5 py-1 font-medium ${
            growthOn
              ? "bg-[var(--accent)]/20 text-[var(--foreground)] ring-1 ring-[var(--accent)]/35"
              : "bg-[var(--border)]/20 text-[var(--muted)]"
          }`}
        >
          增长优化 · 在盘 {growthCount}
        </span>
      </div>
      <p className="text-[10px] leading-relaxed text-[var(--muted)]">
        数字为当前 mock 在盘项目数；有在盘项目的一侧高亮，便于与下方卡片分区对照。
      </p>
    </div>
  );
}
