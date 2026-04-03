import type {
  ExceptionItem,
  LifecycleOverviewVM,
  LifecycleStage,
  ProjectObject,
} from "@/domain/types";
import {
  collectPendingApprovalsByStage,
  emptyStageRecord,
  groupProjectsByStage,
  summarizeHealthByStage,
} from "@/domain/selectors/group-by-stage";

const GLOBAL_EXCEPTION_STAGE: LifecycleStage = "review_capture";

function stageBlockersFromExceptions(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): Record<LifecycleStage, ExceptionItem[]> {
  const byId = new Map(projects.map((p) => [p.id, p]));
  const result = emptyStageRecord<ExceptionItem[]>(() => []);

  for (const ex of exceptions) {
    if (!ex.projectId) {
      result[GLOBAL_EXCEPTION_STAGE].push(ex);
      continue;
    }
    const proj = byId.get(ex.projectId);
    if (proj) {
      result[proj.stage].push(ex);
    } else {
      result[GLOBAL_EXCEPTION_STAGE].push(ex);
    }
  }

  return result;
}

export function toLifecycleOverviewVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): LifecycleOverviewVM {
  const stageProjects = groupProjectsByStage(projects);
  const stageCounts = emptyStageRecord<number>(() => 0);
  for (const s of Object.keys(stageProjects) as LifecycleStage[]) {
    stageCounts[s] = stageProjects[s].length;
  }

  return {
    stageCounts,
    stageProjects,
    stageBlockers: stageBlockersFromExceptions(projects, exceptions),
    stageApprovals: collectPendingApprovalsByStage(projects),
    stageHealthSummary: summarizeHealthByStage(stageProjects),
  };
}
