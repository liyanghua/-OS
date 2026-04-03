import type {
  ApprovalStatus,
  ExecutionMode,
  ExecutionStatus,
  LifecycleStage,
  RiskLevel,
} from "./enums";
import type { EntityMeta } from "./entity";

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

export interface ApprovalRecord extends EntityMeta {
  actionId: string;
  approver: string;
  status: ApprovalStatus;
  reason?: string;
}

export interface ExecutionLog extends EntityMeta {
  actionId: string;
  actorType: "human" | "agent" | "automation";
  actorId: string;
  status: ExecutionStatus;
  summary: string;
}
