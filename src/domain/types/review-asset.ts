import type {
  ApprovalStatus,
  AssetPublishStatus,
  AssetType,
  ReviewVerdict,
} from "./enums";
import type { EntityMeta } from "./entity";

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

export interface ReviewSummary extends EntityMeta {
  projectId: string;
  verdict: ReviewVerdict;
  resultSummary: string;
  attributionSummary: string;
  attributionFactors: AttributionFactor[];
  lessonsLearned: string[];
  recommendations: string[];
}

export interface AssetCandidate extends EntityMeta {
  projectId: string;
  type: AssetType;
  title: string;
  rationale: string;
  approvalStatus: ApprovalStatus;
  applicability?: string;
}

export interface PublishedAsset extends EntityMeta {
  type: AssetType;
  title: string;
  summary: string;
  sourceProjectId?: string;
  reuseCount?: number;
  status: AssetPublishStatus;
}
