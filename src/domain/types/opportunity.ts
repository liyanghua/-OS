import type { ConfidenceLevel, SignalFreshness } from "./enums";

export interface OpportunitySignal {
  id: string;
  type:
    | "trend"
    | "competitor_gap"
    | "demand_cluster"
    | "price_band_gap"
    | "style_opportunity";
  summary: string;
  strength: number;
  freshness: SignalFreshness;
}

export interface OpportunityAssessment {
  businessValueScore: number;
  feasibilityScore: number;
  expressionPotentialScore: number;
  confidence: ConfidenceLevel;
  recommendation: "ignore" | "observe" | "evaluate" | "initiate";
}
