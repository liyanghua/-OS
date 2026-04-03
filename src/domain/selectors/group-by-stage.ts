import type { ActionItem, LifecycleStage, ProjectObject } from "@/domain/types";

const ALL_STAGES: LifecycleStage[] = [
  "opportunity_pool",
  "new_product_incubation",
  "launch_validation",
  "growth_optimization",
  "legacy_upgrade",
  "review_capture",
];

export function emptyStageRecord<T>(factory: () => T): Record<LifecycleStage, T> {
  return Object.fromEntries(
    ALL_STAGES.map((s) => [s, factory()]),
  ) as Record<LifecycleStage, T>;
}

/** 商品项目按经营阶段分组 */
export function groupProjectsByStage(
  projects: ProjectObject[],
): Record<LifecycleStage, ProjectObject[]> {
  const base = emptyStageRecord<ProjectObject[]>(() => []);
  for (const p of projects) {
    base[p.stage].push(p);
  }
  return base;
}

/** 待审批动作按商品项目所属阶段聚合 */
export function collectPendingApprovalsByStage(
  projects: ProjectObject[],
): Record<LifecycleStage, ActionItem[]> {
  const base = emptyStageRecord<ActionItem[]>(() => []);
  for (const p of projects) {
    for (const a of p.actions) {
      if (a.approvalStatus === "pending") {
        base[p.stage].push(a);
      }
    }
  }
  return base;
}

/** 各阶段商品项目健康度计数 */
export function summarizeHealthByStage(
  stageProjects: Record<LifecycleStage, ProjectObject[]>,
): Record<
  LifecycleStage,
  { healthy: number; watch: number; atRisk: number; critical: number }
> {
  const out = emptyStageRecord(() => ({
    healthy: 0,
    watch: 0,
    atRisk: 0,
    critical: 0,
  }));

  for (const stage of ALL_STAGES) {
    for (const p of stageProjects[stage]) {
      if (p.health === "healthy") out[stage].healthy += 1;
      else if (p.health === "watch") out[stage].watch += 1;
      else if (p.health === "at_risk") out[stage].atRisk += 1;
      else out[stage].critical += 1;
    }
  }
  return out;
}
