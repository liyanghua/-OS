/** Canonical enums — align with DATA_MODEL.md §3 */

export type LifecycleStage =
  | "opportunity_pool"
  | "new_product_incubation"
  | "launch_validation"
  | "growth_optimization"
  | "legacy_upgrade"
  | "review_capture";

export type ProjectType =
  | "opportunity_project"
  | "new_product_project"
  | "growth_optimization_project"
  | "legacy_upgrade_project";

export type RoleView =
  | "ceo"
  | "product_rd_director"
  | "growth_director"
  | "visual_director";

export type ProjectHealth = "healthy" | "watch" | "at_risk" | "critical";

export type RiskLevel = "low" | "medium" | "high" | "critical";

export type TrendDirection = "up" | "flat" | "down";

export type ApprovalStatus =
  | "not_required"
  | "pending"
  | "approved"
  | "rejected"
  | "expired";

export type ExecutionMode = "manual" | "agent" | "automation";

export type ExecutionStatus =
  | "suggested"
  | "queued"
  | "in_progress"
  | "completed"
  | "rolled_back"
  | "failed"
  | "canceled";

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

export type AgentStatus =
  | "idle"
  | "running"
  | "waiting_human"
  | "blocked"
  | "failed"
  | "completed";

export type SignalFreshness = "real_time" | "near_real_time" | "batch";

export type ConfidenceLevel = "low" | "medium" | "high";

export type ReviewVerdict =
  | "success"
  | "partial_success"
  | "failed"
  | "observe_more";

export type AssetType =
  | "case"
  | "rule"
  | "template"
  | "skill"
  | "sop"
  | "evaluation_sample";

export type AssetPublishStatus = "draft" | "published" | "deprecated";

export type PolicyEnforcementMode =
  | "hard_block"
  | "approval_required"
  | "warn_only";
