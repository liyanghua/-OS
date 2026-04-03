import type { PolicyEnforcementMode } from "./enums";
import type { EntityMeta } from "./entity";

/** DATA_MODEL.md §13.2 */
export interface PolicyBoundary extends EntityMeta {
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
