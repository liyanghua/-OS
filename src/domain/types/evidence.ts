import type { ConfidenceLevel } from "./enums";

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

export interface EvidencePack {
  refs: EvidenceRef[];
  summary?: string;
}
