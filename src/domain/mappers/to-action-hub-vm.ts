import type {
  ActionHubRow,
  ActionHubVM,
  ActionItem,
  ApprovalRecord,
  ExecutionLog,
  ProjectObject,
} from "@/domain/types";
import { sortPendingActions } from "@/domain/mappers/pulse-shared";

function collectActionRows(
  projects: ProjectObject[],
  predicate: (a: ActionItem) => boolean,
): ActionHubRow[] {
  const out: ActionHubRow[] = [];
  for (const p of projects) {
    for (const a of p.actions) {
      if (predicate(a)) {
        out.push({ action: a, projectId: p.id, projectName: p.name });
      }
    }
  }
  return out;
}

function sortLogsByTime(logs: ExecutionLog[]): ExecutionLog[] {
  return [...logs].sort(
    (x, y) => new Date(y.updatedAt).getTime() - new Date(x.updatedAt).getTime(),
  );
}

function flattenExecutionLogs(projects: ProjectObject[]): ExecutionLog[] {
  return projects.flatMap((p) => p.executionLogs ?? []);
}

function flattenApprovals(projects: ProjectObject[]): ApprovalRecord[] {
  return projects.flatMap((p) => p.approvals ?? []);
}

/** 单项目动作中心视图（与全量相同的分桶逻辑） */
export function toActionHubVmForProject(
  projects: ProjectObject[],
  projectId: string,
): ActionHubVM | null {
  const project = projects.find((p) => p.id === projectId);
  if (!project) return null;
  return toActionHubVm([project]);
}

export function toActionHubVm(projects: ProjectObject[]): ActionHubVM {
  const pendingApprovals = collectActionRows(
    projects,
    (a) => a.approvalStatus === "pending",
  ).sort((x, y) => sortPendingActions(x.action, y.action));

  const inProgress = collectActionRows(
    projects,
    (a) => a.executionStatus === "in_progress",
  );

  const autoExecuted = collectActionRows(
    projects,
    (a) =>
      a.executionMode === "automation" && a.executionStatus === "completed",
  );

  const completed = collectActionRows(
    projects,
    (a) =>
      a.executionStatus === "completed" && a.executionMode !== "automation",
  );

  const rolledBack = collectActionRows(
    projects,
    (a) => a.executionStatus === "rolled_back",
  );

  const highRisk = collectActionRows(
    projects,
    (a) => a.risk === "high" || a.risk === "critical",
  );

  const agentMonitoring = collectActionRows(
    projects,
    (a) =>
      a.executionMode === "agent" &&
      (a.executionStatus === "in_progress" ||
        a.executionStatus === "queued"),
  );

  const executionFeed = sortLogsByTime(flattenExecutionLogs(projects));
  const approvalAuditTrail = [...flattenApprovals(projects)].sort(
    (x, y) =>
      new Date(y.updatedAt).getTime() - new Date(x.updatedAt).getTime(),
  );

  return {
    pendingApprovals,
    inProgress,
    autoExecuted,
    completed,
    rolledBack,
    highRisk,
    agentMonitoring,
    executionFeed,
    approvalAuditTrail,
  };
}
