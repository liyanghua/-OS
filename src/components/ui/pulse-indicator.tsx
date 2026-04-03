export type PulseIndicatorTone = "live" | "warning" | "error" | "idle";

const DOT: Record<PulseIndicatorTone, string> = {
  live: "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.55)]",
  warning: "bg-amber-400",
  error: "bg-red-400",
  idle: "bg-[var(--muted-2)]",
};

/** 脉冲 / 实时信号占位指示（CSS 动效，不拉后端） */
export function PulseIndicator({
  tone,
  label,
}: {
  tone: PulseIndicatorTone;
  label?: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="relative flex h-2 w-2 shrink-0">
        {tone === "live" ? (
          <span
            className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400/60 opacity-60"
            aria-hidden
          />
        ) : null}
        <span
          className={`relative inline-flex h-2 w-2 rounded-full ${DOT[tone]}`}
          aria-hidden
        />
      </span>
      {label ? (
        <span className="text-xs font-medium tracking-tight text-[var(--muted)]">
          {label}
        </span>
      ) : null}
    </span>
  );
}
