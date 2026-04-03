import type { ProjectObject } from "@/domain/types";

/** 多决策选项（≥2）或多视觉版本（≥2）的项目，用于方案/版本对比区 */
export function filterPlanCompareCandidates(
  projects: ProjectObject[],
): ProjectObject[] {
  return projects.filter((p) => {
    const opts = p.decisionObject?.options.length ?? 0;
    const vers = p.expression?.creativeVersions.length ?? 0;
    return opts >= 2 || vers >= 2;
  });
}
