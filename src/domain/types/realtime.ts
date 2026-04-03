import type {
  RiskLevel,
  RoleView,
  SignalFreshness,
  ProjectHealth,
} from "./enums";
import type { EntityMeta } from "./entity";
import type { KPISet } from "./kpi";

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

export interface PulseBundle {
  audience: RoleView;
  summary: string;
  items: PulseItem[];
  generatedAt: string;
}

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
