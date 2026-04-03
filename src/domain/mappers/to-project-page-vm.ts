import type {
  LiveSignalFeedItem,
  ProjectObject,
  ProjectObjectPageVM,
  ProjectRealtimeSnapshot,
} from "@/domain/types";

function deriveNextDecisionHint(project: ProjectObject): string {
  const pending = project.actions.filter((a) => a.approvalStatus === "pending");
  if (pending.length > 0) {
    const extra = pending.length > 1 ? ` 等 ${pending.length} 项` : "";
    return `优先关闭待批动作「${pending[0].title}」${extra}`;
  }
  const d = project.decisionObject;
  if (d?.requiresHumanApproval && d.recommendedOptionId) {
    const opt = d.options.find((o) => o.id === d.recommendedOptionId);
    return `确认推荐方案：${opt?.title ?? d.recommendedOptionId}`;
  }
  if (d?.requiresHumanApproval) {
    const t = d.problemOrOpportunity;
    const short = t.length > 36 ? `${t.slice(0, 36)}…` : t;
    return `对「${short}」完成经营决断`;
  }
  return "暂无强制决策门禁；随脉冲与闭环动作推进即可";
}

function deriveRealtime(project: ProjectObject): ProjectRealtimeSnapshot {
  const pendingApprovalCount = project.actions.filter(
    (a) => a.approvalStatus === "pending",
  ).length;
  const runningAgentCount = project.agentStates.filter(
    (g) => g.status === "running" || g.status === "waiting_human",
  ).length;

  return {
    projectId: project.id,
    health: project.health,
    riskLevel: project.riskLevel,
    keyBlocker: project.keyBlocker,
    latestPulse: project.latestPulse,
    pendingApprovalCount,
    runningAgentCount,
    criticalExceptionCount: project.riskLevel === "critical" ? 1 : 0,
    kpis: project.kpis,
    updatedAt: project.updatedAt,
  };
}

function deriveRecentFeed(project: ProjectObject): LiveSignalFeedItem[] {
  const rows: LiveSignalFeedItem[] = [];
  const ts = project.updatedAt;

  if (project.latestPulse) {
    rows.push({
      id: `feed_pulse_${project.id}`,
      createdAt: ts,
      updatedAt: ts,
      projectId: project.id,
      type: "risk_update",
      summary: project.latestPulse,
    });
  }
  for (const a of project.agentStates.slice(0, 3)) {
    rows.push({
      id: `feed_ag_${a.id}`,
      createdAt: a.updatedAt,
      updatedAt: a.updatedAt,
      projectId: project.id,
      type: "agent_update",
      summary: a.summary,
    });
  }
  return rows;
}

export function toProjectPageVm(project: ProjectObject): ProjectObjectPageVM {
  return {
    project,
    realtime: deriveRealtime(project),
    recentFeed: deriveRecentFeed(project),
    nextDecisionHint: deriveNextDecisionHint(project),
  };
}
