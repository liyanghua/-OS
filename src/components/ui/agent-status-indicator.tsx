import type { AgentStatus } from "@/domain/types";

/**
 * 场景 Agent 状态动效（§2.3）：running 旋转环、待人脉冲、阻塞慢脉冲等。
 * 纯展示，不依赖实时轮询。
 */
export function AgentStatusIndicator({ status }: { status: AgentStatus }) {
  switch (status) {
    case "running":
      return (
        <span
          className="relative inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center"
          aria-hidden
        >
          <span className="absolute h-3.5 w-3.5 animate-spin rounded-full border-2 border-sky-400/80 border-t-transparent" />
        </span>
      );
    case "waiting_human":
      return (
        <span
          className="inline-block h-3 w-3 shrink-0 animate-pulse rounded-full bg-amber-400 shadow-[0_0_10px_rgba(251,191,36,0.45)]"
          aria-hidden
        />
      );
    case "blocked":
      return (
        <span
          className="motion-safe:animate-pulse inline-block h-3 w-3 shrink-0 rounded-full bg-orange-400/95"
          style={{ animationDuration: "2s" }}
          aria-hidden
        />
      );
    case "failed":
      return (
        <span
          className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.45)]"
          aria-hidden
        />
      );
    case "completed":
      return (
        <span
          className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-emerald-500 shadow-[0_0_6px_rgba(52,211,153,0.35)]"
          aria-hidden
        />
      );
    default:
      return (
        <span
          className="inline-block h-2.5 w-2.5 shrink-0 rounded-full bg-[var(--muted-2)]"
          aria-hidden
        />
      );
  }
}
