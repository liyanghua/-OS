import type {
  ActionItem,
  CEODashboardVM,
  ExceptionItem,
  ProjectObject,
} from "@/domain/types";
import {
  buildPulseBundleForRole,
  RISK_ORDER,
  sortPendingActions,
} from "@/domain/mappers/pulse-shared";

const HEALTH_BATTLE: Record<ProjectObject["health"], number> = {
  critical: 4,
  at_risk: 3,
  watch: 2,
  healthy: 1,
};

function projectBattleScore(p: ProjectObject): number {
  const h = HEALTH_BATTLE[p.health];
  const growth = p.stage === "growth_optimization" ? 40 : 0;
  const launch = p.stage === "launch_validation" ? 20 : 0;
  return growth + launch + h * 15 + p.priority;
}

function collectPendingActions(projects: ProjectObject[]): ActionItem[] {
  return projects.flatMap((p) =>
    p.actions.filter((a) => a.approvalStatus === "pending"),
  );
}

export function toCeoDashboardVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): CEODashboardVM {
  const pulse = buildPulseBundleForRole("ceo", projects, exceptions);
  const pendingActions = collectPendingActions(projects);
  const runningAgents = projects.reduce(
    (n, p) =>
      n +
      p.agentStates.filter(
        (a) => a.status === "running" || a.status === "waiting_human",
      ).length,
    0,
  );

  const topProjects = [...projects]
    .sort((a, b) => projectBattleScore(b) - projectBattleScore(a))
    .slice(0, 5);

  const topApprovals = [...pendingActions]
    .sort(sortPendingActions)
    .slice(0, 6);

  const topExceptions = [...exceptions]
    .sort(
      (a, b) => (RISK_ORDER[b.severity] ?? 0) - (RISK_ORDER[a.severity] ?? 0),
    )
    .slice(0, 5);

  return {
    pulse,
    topProjects,
    topApprovals,
    topExceptions,
    resourceSummary: {
      budgetSummary: `原型摘要：当前 mock 共 ${projects.length} 个商品项目在盘；预算与投放细项待接经营数据。`,
      teamCapacitySummary: `原型摘要：待审批 ${pendingActions.length} 条需人力介入；建议优先消化高风险项。`,
      agentCapacitySummary: `原型摘要：运行中 / 待人智能体 ${runningAgents} 个（由各项目 agentStates 汇总）。`,
    },
    orgAISummary: {
      decisionToExecutionCycle: `决策到执行：待批 ${pendingActions.length} 条为关键路径；人机关口已用标签标出。`,
      aiAdoptionSummary: `组织与 AI：当前 mock 展示智能体编排与经营侧建议并存，非单点聊天。`,
      automationCoverageSummary: `自动化：低险动作可走规则触发；本屏突出需您拍板的高风险项。`,
    },
  };
}
