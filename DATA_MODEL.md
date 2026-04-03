# DATA_MODEL.md

## 1. Overview

This system is **project-object-centered** and **lifecycle-driven**.

The modeling goals are:

- A **Project Object** is the top-level operating unit.
- All major collaboration, decisions, actions, review, and asset capture attach to a project object.
- **Lifecycle Stage** is the primary structural axis.
- **Role View** changes default summary and priorities, but not the underlying object model.
- Human decisions, AI recommendations, agent progress, and automation execution results must all be explicitly represented.
- Review and asset capture are first-class, not post-hoc notes.

This document defines the canonical data model for the prototype stage.
核心用途：语义底座 + 对象骨架 + 状态协议 + AI/Agent 输出协议 + 页面复用基础 + 资产沉淀接口。

---

## 2. Core Design Principles

1. Use **Project Object** as the top-level entity.
2. Use **Lifecycle Stage** as the main operating state.
3. Separate:
   - human decisions
   - AI recommendations
   - agent progress
   - automation execution results
4. Keep review and asset capture first-class.
5. Support real-time state for:
   - project health
   - risk
   - blockers
   - approvals
   - agent state
   - key KPIs
6. Keep product definition, expression planning, and review content stage-based and versionable.

---

## 3. Core Enums

### 3.1 Lifecycle Stage

```ts
export type LifecycleStage =
  | "opportunity_pool"
  | "new_product_incubation"
  | "launch_validation"
  | "growth_optimization"
  | "legacy_upgrade"
  | "review_capture";
```

### 3.2 Project Type

```ts
export type ProjectType =
  | "opportunity_project"
  | "new_product_project"
  | "growth_optimization_project"
  | "legacy_upgrade_project";
```

### 3.3 Role View

```ts
export type RoleView =
  | "ceo"
  | "product_rd_director"
  | "growth_director"
  | "visual_director";
```

### 3.4 Project Health

```ts
export type ProjectHealth =
  | "healthy"
  | "watch"
  | "at_risk"
  | "critical";
```

### 3.5 Risk Level

```ts
export type RiskLevel =
  | "low"
  | "medium"
  | "high"
  | "critical";
```

### 3.6 Trend Direction

```ts
export type TrendDirection =
  | "up"
  | "flat"
  | "down";
```

### 3.7 Confidence Level

```ts
export type ConfidenceLevel =
  | "low"
  | "medium"
  | "high";
```

### 3.8 Approval Status

```ts
export type ApprovalStatus =
  | "not_required"
  | "pending"
  | "approved"
  | "rejected"
  | "expired";
```

### 3.9 Execution Mode

```ts
export type ExecutionMode =
  | "manual"
  | "agent"
  | "automation";
```

### 3.10 Execution Status

```ts
export type ExecutionStatus =
  | "suggested"
  | "queued"
  | "in_progress"
  | "completed"
  | "rolled_back"
  | "failed"
  | "canceled";
```

### 3.11 Agent Type

```ts
export type AgentType =
  | "opportunity"
  | "new_product"
  | "diagnosis"
  | "content"
  | "visual"
  | "execution"
  | "upgrade"
  | "review_capture"
  | "governance"
  | "data_observer";
```

### 3.12 Agent Status

```ts
export type AgentStatus =
  | "idle"
  | "running"
  | "waiting_human"
  | "blocked"
  | "failed"
  | "completed";
```

### 3.13 Review Verdict

```ts
export type ReviewVerdict =
  | "success"
  | "partial_success"
  | "failed"
  | "observe_more";
```

### 3.14 Asset Type

```ts
export type AssetType =
  | "case"
  | "rule"
  | "template"
  | "skill"
  | "sop"
  | "evaluation_sample";
```

### 3.15 Signal Freshness

```ts
export type SignalFreshness =
  | "real_time"
  | "near_real_time"
  | "batch";
```

### 3.16 Policy Enforcement Mode

```ts
export type PolicyEnforcementMode =
  | "hard_block"
  | "approval_required"
  | "warn_only";
```

### 3.17 Asset Publish Status

```ts
export type AssetPublishStatus =
  | "draft"
  | "published"
  | "deprecated";
```

---

## 4. Base Types

### 4.1 Entity Meta

```ts
export interface EntityMeta {
  id: string;
  createdAt: string;
  updatedAt: string;
  createdBy?: string;
  updatedBy?: string;
}
```

### 4.2 Person Ref

```ts
export interface PersonRef {
  id: string;
  name: string;
  role:
    | "ceo"
    | "product_rd_director"
    | "growth_director"
    | "visual_director"
    | "operator"
    | "designer"
    | "analyst"
    | "agent";
}
```

### 4.3 Tag

```ts
export interface Tag {
  key: string;
  label: string;
}
```

---

## 5. KPI Model

### 5.1 KPI Metric

```ts
export interface KPIMetric {
  key:
    | "gmv"
    | "ctr"
    | "cvr"
    | "roi"
    | "add_to_cart_rate"
    | "launch_score"
    | "profit"
    | "impressions"
    | "clicks"
    | "orders"
    | "conversion_count";
  label: string;
  value: number;
  unit?: "%" | "currency" | "count" | "score";
  trend?: TrendDirection;
  deltaVsTarget?: number;
  deltaVsPrevious?: number;
  freshness?: SignalFreshness;
}
```

### 5.2 KPI Set

```ts
export interface KPISet {
  metrics: KPIMetric[];
  updatedAt: string;
}
```

---

## 6. Evidence Model

### 6.1 Evidence Ref

```ts
export interface EvidenceRef {
  id: string;
  type:
    | "metric"
    | "history"
    | "case"
    | "rule"
    | "agent_observation"
    | "user_feedback"
    | "competitive_scan";
  summary: string;
  sourceLabel?: string;
  confidence?: ConfidenceLevel;
}
```

### 6.2 Evidence Pack

```ts
export interface EvidencePack {
  refs: EvidenceRef[];
  summary?: string;
}
```

---

## 7. Decision Object Model

### 7.1 Decision Option

```ts
export interface DecisionOption {
  id: string;
  title: string;
  summary: string;
  expectedImpact: string;
  risk: RiskLevel;
  resourcesNeeded: string;
  validationWindow: string;
  autoExecutable: boolean;
  constraints?: string[];
}
```

### 7.2 Decision Object

```ts
export interface DecisionObject extends EntityMeta {
  projectId: string;
  stage: LifecycleStage;
  problemOrOpportunity: string;
  rationale: string;
  rootCauseSummary?: string;
  options: DecisionOption[];
  recommendedOptionId?: string;
  confidence: ConfidenceLevel;
  requiresHumanApproval: boolean;
  evidencePack: EvidencePack;
  pendingQuestions?: string[];
}
```

### 7.3 Decision Summary Card Model

```ts
export interface DecisionSummaryCard {
  id: string;
  projectId: string;
  title: string;
  summary: string;
  confidence: ConfidenceLevel;
  risk: RiskLevel;
  requiresApproval: boolean;
  recommendedOptionTitle?: string;
}
```

---

## 8. Opportunity Model

### 8.1 Opportunity Signal

```ts
export interface OpportunitySignal {
  id: string;
  type:
    | "trend"
    | "competitor_gap"
    | "demand_cluster"
    | "price_band_gap"
    | "style_opportunity";
  summary: string;
  strength: number; // 0-100
  freshness: SignalFreshness;
}
```

### 8.2 Opportunity Assessment

```ts
export interface OpportunityAssessment {
  businessValueScore: number; // 0-100
  feasibilityScore: number; // 0-100
  expressionPotentialScore: number; // 0-100
  confidence: ConfidenceLevel;
  recommendation: "ignore" | "observe" | "evaluate" | "initiate";
}
```

---

## 9. Product Definition Model

### 9.1 Product Definition

```ts
export interface ProductDefinition extends EntityMeta {
  projectId: string;
  positioning: string;
  targetAudience: string;
  keySellingPoints: string[];
  priceBand: string;
  specsSummary: string;
  materialOrCraftSummary?: string;
  versionStrategy?: string;
  feasibilityRisk: RiskLevel;
  samplingStatus:
    | "not_started"
    | "in_progress"
    | "ready_for_review"
    | "approved";
  blockingIssues?: string[];
}
```

### 9.2 Sampling Review

```ts
export interface SamplingReview extends EntityMeta {
  projectId: string;
  summary: string;
  feasibilityVerdict: "pass" | "revise" | "fail";
  costRisk: RiskLevel;
  craftRisk: RiskLevel;
  leadTimeRisk: RiskLevel;
  massProductionRisk: RiskLevel;
  expressionReadinessRisk: RiskLevel;
}
```

---

## 10. Expression Planning Model

### 10.1 Creative Version

```ts
export interface CreativeVersion extends EntityMeta {
  projectId: string;
  name: string;
  type:
    | "hero_image"
    | "detail_page"
    | "campaign_page"
    | "video_cover"
    | "content_asset";
  status:
    | "draft"
    | "testing"
    | "selected"
    | "retired";
  performanceSummary?: string;
  brandConsistencyScore?: number; // 0-100
}
```

### 10.2 Expression Plan

```ts
export interface ExpressionPlan extends EntityMeta {
  projectId: string;
  contentBrief?: string;
  visualBrief?: string;
  readinessStatus:
    | "not_started"
    | "in_progress"
    | "ready"
    | "launched";
  creativeVersions: CreativeVersion[];
  recommendedDirection?: string;
}
```

---

## 11. Action Lifecycle Model

### 11.1 Action Item

```ts
export interface ActionItem extends EntityMeta {
  sourceProjectId: string;
  sourceStage: LifecycleStage;
  goal: string;
  title: string;
  summary: string;
  expectedImpact: string;
  risk: RiskLevel;
  owner: string;
  approvalStatus: ApprovalStatus;
  executionMode: ExecutionMode;
  executionStatus: ExecutionStatus;
  validationWindow?: string;
  rollbackCondition?: string;
  requiresHumanApproval: boolean;
  triggeredBy:
    | "human"
    | "decision_brain"
    | "scenario_agent"
    | "automation_rule";
}
```

### 11.2 Approval Record

```ts
export interface ApprovalRecord extends EntityMeta {
  actionId: string;
  approver: string;
  status: ApprovalStatus;
  reason?: string;
}
```

### 11.3 Execution Log

```ts
export interface ExecutionLog extends EntityMeta {
  actionId: string;
  actorType: "human" | "agent" | "automation";
  actorId: string;
  status: ExecutionStatus;
  summary: string;
}
```

---

## 12. Agent State Model

### 12.1 Agent State

```ts
export interface AgentState extends EntityMeta {
  projectId?: string;
  agentType: AgentType;
  status: AgentStatus;
  summary: string;
  waitingReason?: string;
  lastActionSummary?: string;
}
```

### 12.2 Agent Feed Item

```ts
export interface AgentFeedItem extends EntityMeta {
  projectId?: string;
  agentType: AgentType;
  kind:
    | "started"
    | "updated"
    | "waiting_human"
    | "failed"
    | "completed";
  summary: string;
}
```

---

## 13. Approval and Governance Model

### 13.1 Exception Item

```ts
export interface ExceptionItem extends EntityMeta {
  projectId?: string;
  source:
    | "approval_timeout"
    | "agent_failure"
    | "data_anomaly"
    | "policy_violation"
    | "low_confidence_decision"
    | "rollback_event";
  severity: RiskLevel;
  summary: string;
  requiresHumanIntervention: boolean;
}
```

### 13.2 Policy Boundary

```ts
export interface PolicyBoundary {
  id: string;
  label: string;
  description: string;
  appliesTo:
    | "pricing"
    | "launch"
    | "campaign"
    | "visual"
    | "approval"
    | "automation";
  enforcementMode: PolicyEnforcementMode;
}
```

---

## 14. Review and Asset Capture Model

### 14.1 Attribution Factor

```ts
export interface AttributionFactor {
  id: string;
  category:
    | "product_definition"
    | "sampling"
    | "content"
    | "visual"
    | "campaign"
    | "timing"
    | "supply"
    | "agent_execution";
  summary: string;
  impactLevel: "low" | "medium" | "high";
  controllable: boolean;
}
```

### 14.2 Review Summary

```ts
export interface ReviewSummary extends EntityMeta {
  projectId: string;
  verdict: ReviewVerdict;
  resultSummary: string;
  attributionSummary: string;
  attributionFactors: AttributionFactor[];
  lessonsLearned: string[];
  recommendations: string[];
}
```

### 14.3 Asset Candidate

```ts
export interface AssetCandidate extends EntityMeta {
  projectId: string;
  type: AssetType;
  title: string;
  rationale: string;
  approvalStatus: ApprovalStatus;
  applicability?: string;
}
```

### 14.4 Published Asset

```ts
export interface PublishedAsset extends EntityMeta {
  type: AssetType;
  title: string;
  summary: string;
  sourceProjectId?: string;
  reuseCount?: number;
  status: AssetPublishStatus;
}
```

---

## 15. Real-time Update Model

### 15.1 Pulse Item

```ts
export interface PulseItem extends EntityMeta {
  audience: RoleView;
  category:
    | "risk"
    | "opportunity"
    | "approval"
    | "blocker"
    | "resource"
    | "review";
  summary: string;
  severity?: RiskLevel;
  relatedProjectId?: string;
  freshness: SignalFreshness;
}
```

### 15.2 Pulse Bundle

```ts
export interface PulseBundle {
  audience: RoleView;
  summary: string;
  items: PulseItem[];
  generatedAt: string;
}
```

### 15.3 Real-time Project Snapshot

```ts
export interface ProjectRealtimeSnapshot {
  projectId: string;
  health: ProjectHealth;
  riskLevel: RiskLevel;
  keyBlocker?: string;
  latestPulse?: string;
  pendingApprovalCount: number;
  runningAgentCount: number;
  criticalExceptionCount: number;
  kpis: KPISet;
  updatedAt: string;
}
```

### 15.4 Live Signal Feed Item

```ts
export interface LiveSignalFeedItem extends EntityMeta {
  projectId?: string;
  type:
    | "metric_update"
    | "risk_update"
    | "approval_update"
    | "agent_update"
    | "blocker_update"
    | "execution_update";
  summary: string;
}
```

---

## 16. Project Object Main Model

### 16.1 Project Object

```ts
export interface ProjectObject extends EntityMeta {
  type: ProjectType;
  name: string;
  stage: LifecycleStage;
  owner: string;
  stakeholders: PersonRef[];
  priority: number; // 1-100
  health: ProjectHealth;
  riskLevel: RiskLevel;
  targetSummary: string;
  statusSummary: string;
  latestPulse?: string;
  keyBlocker?: string;
  kpis: KPISet;

  opportunitySignals?: OpportunitySignal[];
  opportunityAssessment?: OpportunityAssessment;

  decisionObject?: DecisionObject;
  definition?: ProductDefinition;
  samplingReview?: SamplingReview;
  expression?: ExpressionPlan;

  actions: ActionItem[];
  approvals?: ApprovalRecord[];
  executionLogs?: ExecutionLog[];

  agentStates: AgentState[];
  review?: ReviewSummary;

  assetCandidates?: AssetCandidate[];
  publishedAssets?: PublishedAsset[];
}
```

---

## 17. Lifecycle Semantics

### 17.1 `opportunity_pool`

**Used for:**

- opportunity discovery
- opportunity scoring
- candidate filtering

**Expected attached models:**

- `opportunitySignals`
- `opportunityAssessment`
- optional `decisionObject`

### 17.2 `new_product_incubation`

**Used for:**

- initiation
- product definition
- sampling preparation and review

**Expected attached models:**

- `decisionObject`
- `definition`
- `samplingReview`
- `actions`
- `agentStates`

### 17.3 `launch_validation`

**Used for:**

- launch readiness
- launch performance checking
- scale / adjust / pause decision

**Expected attached models:**

- `expression`
- `decisionObject`
- `actions`
- `kpis`
- draft review hints

### 17.4 `growth_optimization`

**Used for:**

- diagnosis
- optimization
- battle planning
- scaling

**Expected attached models:**

- `decisionObject`
- `actions`
- `agentStates`
- `kpis`
- optional `review`

### 17.5 `legacy_upgrade`

**Used for:**

- upgrade candidate management
- upgrade path planning
- relaunch validation

**Expected attached models:**

- `decisionObject`
- `definition`
- `expression`
- `actions`
- `review`

### 17.6 `review_capture`

**Used for:**

- final review
- attribution
- lessons
- asset candidate generation

**Expected attached models:**

- `review`
- `assetCandidates`
- `publishedAssets`

---

## 18. Page-layer ViewModel Recommendations

These are presentation-layer models, not canonical storage models.

### 18.1 CEO Dashboard ViewModel

```ts
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
```

### 18.2 Product R&D Director ViewModel

```ts
export interface ProductRDDirectorVM {
  pulse: PulseBundle;
  opportunityProjects: ProjectObject[];
  incubationProjects: ProjectObject[];
  upgradeProjects: ProjectObject[];
  topSamplingRisks: ProjectObject[];
}
```

### 18.3 Growth Director ViewModel

```ts
export interface GrowthDirectorVM {
  pulse: PulseBundle;
  launchProjects: ProjectObject[];
  optimizationProjects: ProjectObject[];
  pendingApprovals: ActionItem[];
  blockers: ExceptionItem[];
}
```

### 18.4 Visual Director ViewModel

```ts
export interface VisualDirectorVM {
  pulse: PulseBundle;
  expressionProjects: ProjectObject[];
  creativeVersionPool: CreativeVersion[];
  upgradeCandidates: ProjectObject[];
  reusableAssets: PublishedAsset[];
}
```

### 18.5 Lifecycle Overview ViewModel

```ts
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
```

### 18.6 Project Object Page ViewModel

```ts
export interface ProjectObjectPageVM {
  project: ProjectObject;
  realtime?: ProjectRealtimeSnapshot;
  pulseItems?: PulseItem[];
  recentFeed?: LiveSignalFeedItem[];
}
```

### 18.7 Action Hub ViewModel

```ts
export interface ActionHubVM {
  pendingApprovals: ActionItem[];
  inProgress: ActionItem[];
  autoExecuted: ActionItem[];
  completed: ActionItem[];
  rolledBack: ActionItem[];
  executionFeed: ExecutionLog[];
}
```

### 18.8 Governance ViewModel

```ts
export interface GovernanceVM {
  exceptions: ExceptionItem[];
  highRiskApprovals: ActionItem[];
  lowConfidenceDecisions: DecisionObject[];
  policyBoundaries: PolicyBoundary[];
  auditLogs: ExecutionLog[];
}
```

### 18.9 Review to Asset ViewModel

```ts
export interface ReviewToAssetVM {
  review: ReviewSummary;
  candidates: AssetCandidate[];
  publishedAssets: PublishedAsset[];
}
```

---

## 19. Mock Data Implementation Recommendations

For the prototype stage:

### 19.1 Minimum Seed Counts

Seed at least:

- 4 `opportunity_project`
- 4 `new_product_project`
- 4 `growth_optimization_project`
- 3 `legacy_upgrade_project`

### 19.2 Minimum Per-project Content

Each project should include:

- `stage`
- `health`
- `riskLevel`
- `targetSummary`
- `statusSummary`
- at least 1 `DecisionObject`
- at least 2 `ActionItem`
- at least 1 `AgentState`
- at least 1 KPI metric set

### 19.3 Recommended Mixed States

At least some projects should include:

- `approvalStatus: "pending"`
- `executionStatus: "failed"`
- `AgentStatus: "waiting_human"`
- `health: "critical"`
- `assetCandidates`
- `review`

### 19.4 Role Coverage

Mock data should support all role views:

- CEO sees battle, risk, approvals, efficiency
- Product R&D Director sees opportunities, incubation, sampling risk
- Growth Director sees launch, optimization, blockers, approvals
- Visual Director sees expression projects, creative versions, reusable assets

### 19.5 Real-time Simulation

For prototype stage, simulate real-time by:

- polling mock updates
- interval-based local state refresh
- mock signal feed
- random KPI trend shifts
- random agent status updates
- random blocker generation / resolution

### 19.6 Shared Source of Truth

Use one central mock data source or store. Do not create page-local ad hoc data unless it is a pure ViewModel transformation.

---

## 20. Frontend Modeling Guidance

- All cards should derive from canonical models where possible.
- If page-specific formatting is needed, create explicit ViewModels.
- Keep enums centralized.
- Keep lifecycle-aware rendering reusable.
- Every major page should be able to show: pulse, risk, health, approval state, agent state, latest update.
- Do not collapse human decisions, AI recommendations, agent progress, and automation results into one generic status string.

---

## 21. Minimal Prototype Integrity Checklist

Before considering the prototype data model usable:

- lifecycle enums are centralized
- project object schema is typed
- decision object schema is typed
- product definition schema is typed
- expression plan schema is typed
- action lifecycle is typed
- agent state is typed
- governance types are typed
- review and asset capture are typed
- role dashboards derive from the same source models
- real-time snapshot model exists
- mock data can drive all major pages