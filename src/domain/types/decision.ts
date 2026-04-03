import type { ConfidenceLevel, LifecycleStage, RiskLevel } from "./enums";
import type { EntityMeta } from "./entity";
import type { EvidencePack } from "./evidence";

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
