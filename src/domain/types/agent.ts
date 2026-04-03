import type { AgentStatus, AgentType } from "./enums";
import type { EntityMeta } from "./entity";

export interface AgentState extends EntityMeta {
  projectId?: string;
  agentType: AgentType;
  status: AgentStatus;
  summary: string;
  waitingReason?: string;
  lastActionSummary?: string;
}
