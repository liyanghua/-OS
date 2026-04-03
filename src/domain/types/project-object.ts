import type {
  LifecycleStage,
  ProjectHealth,
  ProjectType,
  RiskLevel,
} from "./enums";
import type { EntityMeta, PersonRef } from "./entity";
import type { ActionItem, ApprovalRecord, ExecutionLog } from "./action";
import type { AgentState } from "./agent";
import type { KPISet } from "./kpi";
import type { DecisionObject } from "./decision";
import type { ProductDefinition, SamplingReview } from "./product-definition";
import type { ExpressionPlan } from "./expression";
import type { OpportunityAssessment, OpportunitySignal } from "./opportunity";
import type { ReviewSummary, AssetCandidate, PublishedAsset } from "./review-asset";

/** DATA_MODEL.md §16.1 */
export interface ProjectObject extends EntityMeta {
  type: ProjectType;
  name: string;
  stage: LifecycleStage;
  owner: string;
  stakeholders: PersonRef[];
  priority: number;
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
