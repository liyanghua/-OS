import type {
  ActionItem,
  ExceptionItem,
  GrowthDirectorVM,
  ProjectObject,
} from "@/domain/types";
import {
  buildPulseBundleForRole,
  RISK_ORDER,
  sortPendingActions,
} from "@/domain/mappers/pulse-shared";

function collectPendingActions(projects: ProjectObject[]): ActionItem[] {
  return projects.flatMap((p) =>
    p.actions.filter((a) => a.approvalStatus === "pending"),
  );
}

export function toGrowthDirectorVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): GrowthDirectorVM {
  const pulse = buildPulseBundleForRole("growth_director", projects, exceptions);

  const launchProjects = projects.filter(
    (p) => p.stage === "launch_validation",
  );
  const optimizationProjects = projects.filter(
    (p) => p.stage === "growth_optimization",
  );

  const pendingApprovals = [...collectPendingActions(projects)]
    .sort(sortPendingActions)
    .slice(0, 8);

  const blockers = [...exceptions].sort(
    (a, b) => (RISK_ORDER[b.severity] ?? 0) - (RISK_ORDER[a.severity] ?? 0),
  );

  return {
    pulse,
    launchProjects,
    optimizationProjects,
    pendingApprovals,
    blockers,
  };
}
