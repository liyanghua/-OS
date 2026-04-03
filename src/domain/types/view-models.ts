import type { ActionItem, ApprovalRecord, ExecutionLog } from "./action";
import type { AgentState } from "./agent";
import type { ExceptionItem } from "./exception";
import type { DecisionObject } from "./decision";
import type { CreativeVersion } from "./expression";
import type { AssetType, LifecycleStage } from "./enums";
import type { PolicyBoundary } from "./policy-boundary";
import type { ProjectObject } from "./project-object";
import type {
  AssetCandidate,
  PublishedAsset,
  ReviewSummary,
} from "./review-asset";
import type {
  LiveSignalFeedItem,
  ProjectRealtimeSnapshot,
  PulseBundle,
  PulseItem,
} from "./realtime";

export interface LifecycleOverviewVM {
  stageCounts: Record<LifecycleStage, number>;
  stageProjects: Record<LifecycleStage, ProjectObject[]>;
  stageBlockers: Record<LifecycleStage, ExceptionItem[]>;
  stageApprovals: Record<LifecycleStage, ActionItem[]>;
  stageHealthSummary: Record<
    LifecycleStage,
    {
      healthy: number;
      watch: number;
      atRisk: number;
      critical: number;
    }
  >;
}

export interface ProjectObjectPageVM {
  project: ProjectObject;
  realtime?: ProjectRealtimeSnapshot;
  pulseItems?: PulseItem[];
  recentFeed?: LiveSignalFeedItem[];
  /** 由决策对象与待批动作推导的下一关键决策焦点 */
  nextDecisionHint: string;
}

/** DATA_MODEL.md §18.1 — CEO 经营指挥台 */
export interface CEODashboardVM {
  pulse: PulseBundle;
  topProjects: ProjectObject[];
  topApprovals: ActionItem[];
  topExceptions: ExceptionItem[];
  resourceSummary: {
    budgetSummary: string;
    teamCapacitySummary: string;
    agentCapacitySummary: string;
  };
  orgAISummary: {
    decisionToExecutionCycle: string;
    aiAdoptionSummary: string;
    automationCoverageSummary: string;
  };
}

/** DATA_MODEL.md §18.2 */
export interface ProductRDDirectorVM {
  pulse: PulseBundle;
  opportunityProjects: ProjectObject[];
  incubationProjects: ProjectObject[];
  upgradeProjects: ProjectObject[];
  topSamplingRisks: ProjectObject[];
}

/** DATA_MODEL.md §18.3 */
export interface GrowthDirectorVM {
  pulse: PulseBundle;
  launchProjects: ProjectObject[];
  optimizationProjects: ProjectObject[];
  pendingApprovals: ActionItem[];
  blockers: ExceptionItem[];
}

/** DATA_MODEL.md §18.4 */
export interface VisualDirectorVM {
  pulse: PulseBundle;
  expressionProjects: ProjectObject[];
  creativeVersionPool: CreativeVersion[];
  upgradeCandidates: ProjectObject[];
  reusableAssets: PublishedAsset[];
}

/** M5 生命周期阶段工作台 — 页面层 VM（prototype） */

export interface OpportunityPoolStageWorkspaceVM {
  pulse: PulseBundle;
  projects: ProjectObject[];
  blockers: ExceptionItem[];
  pendingApprovals: ActionItem[];
}

export interface IncubationSwimlane {
  onTrack: ProjectObject[];
  attention: ProjectObject[];
  risk: ProjectObject[];
}

export interface NewProductIncubationStageWorkspaceVM {
  pulse: PulseBundle;
  swimlane: IncubationSwimlane;
  projects: ProjectObject[];
  definitionHighlights: ProjectObject[];
  samplingRiskProjects: ProjectObject[];
  cosignPending: ActionItem[];
  blockers: ExceptionItem[];
  agents: { state: AgentState; project: ProjectObject }[];
}

export interface LaunchTargetVsResultRow {
  projectId: string;
  name: string;
  targetSummary: string;
  kpiSummary: string;
}

export interface LaunchValidationStageWorkspaceVM {
  pulse: PulseBundle;
  projects: ProjectObject[];
  planCompareProjects: ProjectObject[];
  targetVsResult: LaunchTargetVsResultRow[];
  scaleAdjustPauseHints: string[];
  blockers: ExceptionItem[];
  pendingApprovals: ActionItem[];
  agents: { state: AgentState; project: ProjectObject }[];
}

export interface GrowthOptimizationStageWorkspaceVM {
  pulse: PulseBundle;
  projects: ProjectObject[];
  diagnosisItems: string[];
  optimizationActions: ActionItem[];
  blockers: ExceptionItem[];
  agents: { state: AgentState; project: ProjectObject }[];
}

export interface LegacyUpgradeDirectionRow {
  projectId: string;
  name: string;
  directionLine: string;
}

export interface LegacyUpgradeStageWorkspaceVM {
  pulse: PulseBundle;
  projects: ProjectObject[];
  upgradeDirections: LegacyUpgradeDirectionRow[];
  relaunchValidationBullets: string[];
  blockers: ExceptionItem[];
  pendingApprovals: ActionItem[];
  agents: { state: AgentState; project: ProjectObject }[];
}

/** 动作中心行：携带所属项目上下文（M6） */
export interface ActionHubRow {
  action: ActionItem;
  projectId: string;
  projectName: string;
}

/** DATA_MODEL.md §18.7 + M6 扩展分区 */
export interface ActionHubVM {
  pendingApprovals: ActionHubRow[];
  inProgress: ActionHubRow[];
  autoExecuted: ActionHubRow[];
  completed: ActionHubRow[];
  rolledBack: ActionHubRow[];
  highRisk: ActionHubRow[];
  agentMonitoring: ActionHubRow[];
  executionFeed: ExecutionLog[];
  approvalAuditTrail: ApprovalRecord[];
}

export interface GovernanceDecisionRow {
  decision: DecisionObject;
  projectId: string;
  projectName: string;
}

/** DATA_MODEL.md §18.8 + M6 智能体异常 / 规则违规拆条 */
export interface GovernanceVM {
  exceptions: ExceptionItem[];
  highRiskApprovals: ActionHubRow[];
  lowConfidenceDecisions: GovernanceDecisionRow[];
  policyBoundaries: PolicyBoundary[];
  auditLogs: ExecutionLog[];
  agentAnomalies: ExceptionItem[];
  policyViolations: ExceptionItem[];
}

/** DATA_MODEL §18.9 — 单项目复盘到资产的最小链路（复盘不是文档终点） */
export interface ReviewToAssetVM {
  review: ReviewSummary;
  assetCandidates: AssetCandidate[];
  publishedAssets: PublishedAsset[];
}

/** M7 复盘沉淀台 — 按项目分块 + 组织视角聚合 */
export interface ReviewCaptureWorkspaceVM {
  blocks: Array<{
    projectId: string;
    projectName: string;
    stageLabel: string;
    targetSummary: string;
    statusSummary: string;
    kpiSummary: string;
    chain: ReviewToAssetVM;
  }>;
  allPendingCandidates: AssetCandidate[];
  allPublishedAssets: PublishedAsset[];
}

/** M7 经验资产库 — 按资产类型分区，避免普通列表观感 */
export interface AssetHubVM {
  publishedByType: Record<AssetType, PublishedAsset[]>;
  candidatesByType: Record<AssetType, AssetCandidate[]>;
  publishedAll: PublishedAsset[];
  candidatesAll: AssetCandidate[];
}
