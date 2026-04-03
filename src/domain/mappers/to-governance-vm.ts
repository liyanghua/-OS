import type {
  ActionHubRow,
  ActionItem,
  ExecutionLog,
  GovernanceDecisionRow,
  GovernanceVM,
  ExceptionItem,
  PolicyBoundary,
  ProjectObject,
} from "@/domain/types";
import { RISK_ORDER, sortPendingActions } from "@/domain/mappers/pulse-shared";

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

function sortExceptions(exceptions: ExceptionItem[]): ExceptionItem[] {
  return [...exceptions].sort(
    (a, b) =>
      (RISK_ORDER[b.severity] ?? 0) - (RISK_ORDER[a.severity] ?? 0),
  );
}

function flattenExecutionLogs(projects: ProjectObject[]): ExecutionLog[] {
  return projects.flatMap((p) => p.executionLogs ?? []);
}

export function toGovernanceVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  policyBoundaries: PolicyBoundary[],
): GovernanceVM {
  const highRiskApprovals = collectActionRows(
    projects,
    (a) =>
      a.approvalStatus === "pending" &&
      (a.risk === "high" || a.risk === "critical"),
  ).sort((x, y) => sortPendingActions(x.action, y.action));

  const lowConfidenceDecisions: GovernanceDecisionRow[] = [];
  for (const p of projects) {
    const d = p.decisionObject;
    if (d && d.confidence === "low") {
      lowConfidenceDecisions.push({
        decision: d,
        projectId: p.id,
        projectName: p.name,
      });
    }
  }

  const auditLogs = [...flattenExecutionLogs(projects)].sort(
    (x, y) =>
      new Date(y.updatedAt).getTime() - new Date(x.updatedAt).getTime(),
  );

  const agentAnomalies = exceptions.filter((e) => e.source === "agent_failure");
  const policyViolations = exceptions.filter(
    (e) => e.source === "policy_violation",
  );

  return {
    exceptions: sortExceptions(exceptions),
    highRiskApprovals,
    lowConfidenceDecisions,
    policyBoundaries,
    auditLogs,
    agentAnomalies,
    policyViolations,
  };
}
