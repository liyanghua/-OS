import type { ActionItem, ExceptionItem } from "@/domain/types";
import {
  approvalStatusLabel,
  executionModeLabel,
  executionStatusLabel,
  triggeredByLabel,
} from "@/domain/mappers/display-zh";

/** 与 AGENTS.md 四层经营分工对齐的可见性标签 */
export type OperatingLayerVariant =
  | "decision_brain"
  | "scenario_agent"
  | "automation"
  | "human";

/** 深色管理台专用：不依赖 prefers-color-scheme，字色始终偏亮、底为低饱和半透明 */
const LAYER: Record<
  OperatingLayerVariant,
  { label: string; hint: string; className: string }
> = {
  decision_brain: {
    label: "经营建议",
    hint: "经营侧推理、方案与置信判断",
    className:
      "border-[color-mix(in_srgb,violet_45%,transparent)] bg-[color-mix(in_srgb,violet_32%,transparent)] text-violet-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
  },
  scenario_agent: {
    label: "智能体",
    hint: "场景智能体编排与执行推进",
    className:
      "border-[color-mix(in_srgb,#38bdf8_40%,transparent)] bg-[color-mix(in_srgb,#0ea5e9_28%,transparent)] text-sky-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
  },
  automation: {
    label: "自动化",
    hint: "规则与自动化链路回写",
    className:
      "border-[color-mix(in_srgb,teal_40%,transparent)] bg-[color-mix(in_srgb,teal_35%,transparent)] text-teal-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
  },
  human: {
    label: "人为发起",
    hint: "人工发起、审批或拍板",
    className:
      "border-[color-mix(in_srgb,amber_45%,transparent)] bg-[color-mix(in_srgb,amber_35%,transparent)] text-amber-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
  },
};

export function triggeredByToLayer(
  t: ActionItem["triggeredBy"],
): OperatingLayerVariant {
  switch (t) {
    case "decision_brain":
      return "decision_brain";
    case "scenario_agent":
      return "scenario_agent";
    case "automation_rule":
      return "automation";
    default:
      return "human";
  }
}

/** 例外来源 → 主责任层（用于风险台卡片角标） */
export function exceptionSourceToLayer(
  s: ExceptionItem["source"],
): OperatingLayerVariant {
  switch (s) {
    case "low_confidence_decision":
      return "decision_brain";
    case "agent_failure":
      return "scenario_agent";
    case "policy_violation":
    case "data_anomaly":
    case "rollback_event":
      return "automation";
    case "approval_timeout":
      return "human";
  }
}

type OperatingLayerBadgeProps = {
  variant: OperatingLayerVariant;
  withHint?: boolean;
};

export function OperatingLayerBadge({
  variant,
  withHint = false,
}: OperatingLayerBadgeProps) {
  const x = LAYER[variant];
  return (
    <span className="inline-flex max-w-full flex-wrap items-center gap-1.5">
      <span
        className={`inline-flex shrink-0 rounded-md border px-2 py-0.5 text-[11px] font-semibold leading-tight tracking-wide ${x.className}`}
      >
        {x.label}
      </span>
      {withHint ? (
        <span className="text-[10px] leading-snug text-[var(--foreground)]/85">
          {x.hint}
        </span>
      ) : null}
    </span>
  );
}

export function OperatingLayerLegend() {
  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {(Object.keys(LAYER) as OperatingLayerVariant[]).map((k) => (
        <div
          key={k}
          className="flex flex-col gap-1.5 rounded-md border border-[var(--border)] bg-[var(--surface-elevated)] px-2.5 py-2.5"
        >
          <OperatingLayerBadge variant={k} />
          <p className="text-[10px] leading-snug text-[var(--foreground)]/75">
            {LAYER[k].hint}
          </p>
        </div>
      ))}
    </div>
  );
}

/** 紧凑四枚徽章（复盘台等版面紧张处） */
export function OperatingLayerLegendInline() {
  return (
    <div className="flex flex-wrap gap-1.5">
      {(Object.keys(LAYER) as OperatingLayerVariant[]).map((k) => (
        <OperatingLayerBadge key={k} variant={k} />
      ))}
    </div>
  );
}

export function describeActionProgressLine(a: ActionItem): string {
  const src = triggeredByLabel(a.triggeredBy);
  const exec = executionModeLabel(a.executionMode);
  const st = executionStatusLabel(a.executionStatus);
  const ap = approvalStatusLabel(a.approvalStatus);

  if (a.executionStatus === "completed") {
    return `${exec}已将本动作的执行状态置为「${st}」（动作建议来源：${src}）；审批侧当前为「${ap}」。`;
  }
  if (a.executionStatus === "rolled_back") {
    return `${exec}已将本动作标记为「${st}」；审批为「${ap}」。请结合摘要核对回滚原因与后续人工处置。`;
  }
  if (
    a.executionStatus === "in_progress" ||
    a.executionStatus === "queued"
  ) {
    return `当前由 ${exec}推进，执行状态为「${st}」；审批「${ap}」（建议来源：${src}）。`;
  }
  if (a.approvalStatus === "pending") {
    return `处于「${ap}」：需人工放行后方可继续执行（建议来源：${src}；执行模式：${exec}）。`;
  }
  if (a.executionStatus === "failed" || a.executionStatus === "canceled") {
    return `${exec}侧状态为「${st}」；审批「${ap}」（建议来源：${src}）。`;
  }
  if (a.executionStatus === "suggested") {
    return `经营建议或上游已给出动作草案，尚未进入执行队列；审批「${ap}」（建议来源：${src}；执行模式：${exec}）。`;
  }
  return `执行模式 ${exec}，执行状态「${st}」，审批「${ap}」（建议来源：${src}）。`;
}
