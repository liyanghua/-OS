import type { ProjectHealth, RiskLevel } from "@/domain/types/enums";
import type { PulseItem } from "@/domain/types/realtime";

/** 异常优先：按风险等级给卡片壳层（边框 + 浅底），与 PROJECT_INTERACTION_DESIGN_PRINCIPLES 对齐 */
export function riskSeveritySurfaceClasses(severity: RiskLevel): string {
  switch (severity) {
    case "critical":
      return "border-red-500/40 bg-red-500/[0.07] shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]";
    case "high":
      return "border-amber-500/38 bg-amber-500/[0.07] shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]";
    case "medium":
      return "border-sky-500/35 bg-sky-500/[0.06]";
    default:
      return "border-[var(--border)] bg-[var(--surface)]/90";
  }
}

/** 脉冲条目：类别 × 严重度 → 视觉编码 */
export function pulseItemSurfaceClasses(
  item: Pick<PulseItem, "category" | "severity">,
): string {
  const s = item.severity;
  switch (item.category) {
    case "risk":
    case "blocker":
      return riskSeveritySurfaceClasses(s ?? "medium");
    case "approval":
      return "border-sky-500/35 bg-sky-500/[0.06]";
    case "opportunity":
      return "border-emerald-500/30 bg-emerald-500/[0.05]";
    case "review":
      return "border-violet-500/30 bg-violet-500/[0.05]";
    case "resource":
      return "border-teal-500/28 bg-teal-500/[0.05]";
    default:
      return riskSeveritySurfaceClasses(s ?? "low");
  }
}

/** 战役项目卡：健康度 × 风险 → 首屏扫描优先级 */
export function battleProjectSurfaceClasses(
  health: ProjectHealth,
  risk: RiskLevel,
): string {
  if (health === "critical" || risk === "critical") {
    return "border-red-500/40 bg-red-500/[0.05] hover:border-red-400/50";
  }
  if (health === "at_risk" || risk === "high") {
    return "border-amber-500/35 bg-amber-500/[0.05] hover:border-amber-400/45";
  }
  if (health === "watch") {
    return "border-sky-500/28 bg-sky-500/[0.04] hover:border-[var(--accent)]/40";
  }
  return "border-[var(--border)] bg-[var(--surface)]/35 hover:border-[var(--accent)]";
}
