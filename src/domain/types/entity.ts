import type { RoleView } from "./enums";

export interface EntityMeta {
  id: string;
  createdAt: string;
  updatedAt: string;
  createdBy?: string;
  updatedBy?: string;
}

export interface PersonRef {
  id: string;
  name: string;
  role:
    | RoleView
    | "operator"
    | "designer"
    | "analyst"
    | "agent";
}
