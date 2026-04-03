import type {
  ExceptionItem,
  LifecycleStage,
  ProjectObject,
  PulseBundle,
  RoleView,
} from "@/domain/types";
import { collectAllPulseItems, ts } from "@/domain/mappers/pulse-shared";

export { RISK_ORDER } from "@/domain/mappers/pulse-shared";

/** 仅关联到本阶段商品项目的例外；无 projectId 的全局例外不进入阶段脉冲（见 IMPLEMENT M5）。 */
export function exceptionsForLifecycleStage(
  stageProjects: ProjectObject[],
  exceptions: ExceptionItem[],
): ExceptionItem[] {
  const ids = new Set(stageProjects.map((p) => p.id));
  return exceptions.filter(
    (e) => e.projectId != null && ids.has(e.projectId),
  );
}

export function collectStagePulseItems(
  stageProjects: ProjectObject[],
  stageExceptions: ExceptionItem[],
  audience: RoleView,
) {
  return collectAllPulseItems(
    stageProjects,
    stageExceptions,
    audience,
    (n) => `本阶段待审批动作 ${n} 条，建议优先处理高风险项`,
  );
}

const STAGE_PULSE_INTRO: Record<
  | "opportunity_pool"
  | "new_product_incubation"
  | "launch_validation"
  | "growth_optimization"
  | "legacy_upgrade",
  string
> = {
  opportunity_pool: "商机池阶段脉冲",
  new_product_incubation: "新品孵化阶段脉冲",
  launch_validation: "首发验证阶段脉冲",
  growth_optimization: "增长优化阶段脉冲",
  legacy_upgrade: "老品升级阶段脉冲",
};

export type WorkspaceLifecycleStage =
  | "opportunity_pool"
  | "new_product_incubation"
  | "launch_validation"
  | "growth_optimization"
  | "legacy_upgrade";

export function buildStagePulseBundle(
  stage: WorkspaceLifecycleStage,
  allProjects: ProjectObject[],
  allExceptions: ExceptionItem[],
  audience: RoleView,
): PulseBundle {
  const stageProjects = allProjects.filter((p) => p.stage === stage);
  const stageExceptions = exceptionsForLifecycleStage(
    stageProjects,
    allExceptions,
  );
  const items = collectStagePulseItems(
    stageProjects,
    stageExceptions,
    audience,
  ).slice(0, 12);
  const now = ts();
  const intro = STAGE_PULSE_INTRO[stage];
  const summary =
    items.length > 0
      ? `${intro}：${items.length} 条（本阶段项目与关联例外，原型）。`
      : `${intro}：暂无（原型）。`;
  return {
    audience,
    summary,
    items,
    generatedAt: now,
  };
}

export function isWorkspaceStage(
  s: LifecycleStage,
): s is WorkspaceLifecycleStage {
  return (
    s === "opportunity_pool" ||
    s === "new_product_incubation" ||
    s === "launch_validation" ||
    s === "growth_optimization" ||
    s === "legacy_upgrade"
  );
}
