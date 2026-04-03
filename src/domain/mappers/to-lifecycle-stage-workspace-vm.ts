import type {
  ExceptionItem,
  GrowthOptimizationStageWorkspaceVM,
  LaunchValidationStageWorkspaceVM,
  LegacyUpgradeStageWorkspaceVM,
  LegacyUpgradeDirectionRow,
  NewProductIncubationStageWorkspaceVM,
  OpportunityPoolStageWorkspaceVM,
  ProjectObject,
  RoleView,
} from "@/domain/types";
import { sortPendingActions, RISK_ORDER } from "@/domain/mappers/pulse-shared";
import {
  buildStagePulseBundle,
  exceptionsForLifecycleStage,
} from "@/domain/mappers/stage-pulse";
import { filterPlanCompareCandidates } from "@/domain/selectors/plan-compare-candidates";

function formatKpiSummary(p: ProjectObject): string {
  const m = p.kpis.metrics;
  if (m.length === 0) return "暂无 KPI 摘要";
  return m
    .map((x) => `${x.label} ${x.value}${x.unit ? x.unit : ""}`)
    .join(" · ");
}

function collectAgents(stageProjects: ProjectObject[]) {
  return stageProjects.flatMap((p) =>
    p.agentStates.map((state) => ({ state, project: p })),
  );
}

function samplingRiskSort(a: ProjectObject, b: ProjectObject): number {
  const ar = a.definition ? (RISK_ORDER[a.definition.feasibilityRisk] ?? 0) : 0;
  const br = b.definition ? (RISK_ORDER[b.definition.feasibilityRisk] ?? 0) : 0;
  return br - ar;
}

export function toOpportunityPoolWorkspaceVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  audience: RoleView,
): OpportunityPoolStageWorkspaceVM {
  const stage = "opportunity_pool" as const;
  const ps = projects.filter((p) => p.stage === stage);
  return {
    pulse: buildStagePulseBundle(stage, projects, exceptions, audience),
    projects: ps,
    blockers: exceptionsForLifecycleStage(ps, exceptions),
    pendingApprovals: ps
      .flatMap((p) => p.actions.filter((a) => a.approvalStatus === "pending"))
      .sort(sortPendingActions),
  };
}

export function toNewProductIncubationWorkspaceVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  audience: RoleView,
): NewProductIncubationStageWorkspaceVM {
  const stage = "new_product_incubation" as const;
  const ps = projects.filter((p) => p.stage === stage);
  const swimlane = {
    onTrack: ps.filter((p) => p.health === "healthy"),
    attention: ps.filter((p) => p.health === "watch"),
    risk: ps.filter(
      (p) => p.health === "at_risk" || p.health === "critical",
    ),
  };
  const definitionHighlights = ps.filter((p) => p.definition != null);
  const samplingRiskProjects = [...ps]
    .filter((p) => p.definition != null)
    .sort(samplingRiskSort)
    .slice(0, 6);
  const cosignPending = ps
    .flatMap((p) => p.actions)
    .filter(
      (a) =>
        a.approvalStatus === "pending" &&
        a.sourceStage === "new_product_incubation",
    )
    .sort(sortPendingActions);

  return {
    pulse: buildStagePulseBundle(stage, projects, exceptions, audience),
    swimlane,
    projects: ps,
    definitionHighlights,
    samplingRiskProjects,
    cosignPending,
    blockers: exceptionsForLifecycleStage(ps, exceptions),
    agents: collectAgents(ps),
  };
}

export function toLaunchValidationWorkspaceVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  audience: RoleView,
): LaunchValidationStageWorkspaceVM {
  const stage = "launch_validation" as const;
  const ps = projects.filter((p) => p.stage === stage);
  const planCompareProjects = filterPlanCompareCandidates(ps);
  const targetVsResult = ps.map((p) => ({
    projectId: p.id,
    name: p.name,
    targetSummary: p.targetSummary,
    kpiSummary: formatKpiSummary(p),
  }));

  const scaleAdjustPauseHints: string[] = [];
  for (const p of ps) {
    const d = p.decisionObject;
    if (d?.recommendedOptionId) {
      const opt = d.options.find((o) => o.id === d.recommendedOptionId);
      if (opt) {
        scaleAdjustPauseHints.push(
          `${p.name}：经营侧建议关注「${opt.title}」（${opt.summary}）`,
        );
      }
    }
    for (const a of p.actions.filter((x) => x.approvalStatus === "pending")) {
      scaleAdjustPauseHints.push(
        `${p.name} 待决策动作：${a.title}（${a.summary}）`,
      );
    }
    if (p.latestPulse) {
      scaleAdjustPauseHints.push(`${p.name} 实时脉冲：${p.latestPulse}`);
    }
  }

  return {
    pulse: buildStagePulseBundle(stage, projects, exceptions, audience),
    projects: ps,
    planCompareProjects,
    targetVsResult,
    scaleAdjustPauseHints,
    blockers: exceptionsForLifecycleStage(ps, exceptions),
    pendingApprovals: ps
      .flatMap((p) => p.actions.filter((a) => a.approvalStatus === "pending"))
      .sort(sortPendingActions),
    agents: collectAgents(ps),
  };
}

export function toGrowthOptimizationWorkspaceVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  audience: RoleView,
): GrowthOptimizationStageWorkspaceVM {
  const stage = "growth_optimization" as const;
  const ps = projects.filter((p) => p.stage === stage);
  const blockers = exceptionsForLifecycleStage(ps, exceptions);
  const diagnosisItems: string[] = [];
  for (const ex of blockers) {
    diagnosisItems.push(`[例外] ${ex.summary}`);
  }
  for (const p of ps) {
    if (p.latestPulse) {
      diagnosisItems.push(`${p.name}：${p.latestPulse}`);
    }
    if (p.keyBlocker) {
      diagnosisItems.push(`${p.name} 阻塞：${p.keyBlocker}`);
    }
  }
  if (diagnosisItems.length === 0) {
    diagnosisItems.push("暂无显性诊断条目（可继续观察 KPI 与智能体输出，原型）。");
  }

  const allActions = ps.flatMap((p) => p.actions);
  const pending = allActions
    .filter((a) => a.approvalStatus === "pending")
    .sort(sortPendingActions);
  const rest = allActions.filter((a) => a.approvalStatus !== "pending");
  const optimizationActions = [...pending, ...rest];

  return {
    pulse: buildStagePulseBundle(stage, projects, exceptions, audience),
    projects: ps,
    diagnosisItems,
    optimizationActions,
    blockers,
    agents: collectAgents(ps),
  };
}

const RELAUNCH_SKELETON = [
  "再上市前需核对：定价带、渠道陈列、内容素材与合规披露（原型骨架）。",
  "建议以极小流量窗口验证转化与库存周转（占位）。",
  "结论回写商品项目后，可进入复盘沉淀沉淀可复用资产（本轮不实现闭环）。",
];

export function toLegacyUpgradeWorkspaceVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
  audience: RoleView,
): LegacyUpgradeStageWorkspaceVM {
  const stage = "legacy_upgrade" as const;
  const ps = projects.filter((p) => p.stage === stage);
  const upgradeDirections: LegacyUpgradeDirectionRow[] = ps.map((p) => ({
    projectId: p.id,
    name: p.name,
    directionLine:
      p.decisionObject?.rationale ??
      p.expression?.visualBrief ??
      p.targetSummary,
  }));

  return {
    pulse: buildStagePulseBundle(stage, projects, exceptions, audience),
    projects: ps,
    upgradeDirections,
    relaunchValidationBullets: RELAUNCH_SKELETON,
    blockers: exceptionsForLifecycleStage(ps, exceptions),
    pendingApprovals: ps
      .flatMap((p) => p.actions.filter((a) => a.approvalStatus === "pending"))
      .sort(sortPendingActions),
    agents: collectAgents(ps),
  };
}
