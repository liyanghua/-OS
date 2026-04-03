import type { PolicyBoundary } from "@/domain/types";
import {
  policyAppliesToLabel,
  policyEnforcementModeLabel,
} from "@/domain/mappers/display-zh";

type PolicyBoundaryCardProps = {
  policy: PolicyBoundary;
};

export function PolicyBoundaryCard({ policy }: PolicyBoundaryCardProps) {
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)]/85 bg-[var(--surface-elevated)]/35 px-3 py-2.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="font-medium text-[var(--foreground)]">{policy.label}</p>
      <p className="mt-1 text-[var(--muted)]">{policy.description}</p>
      <div className="mt-2 flex flex-wrap gap-2 text-[var(--muted)]">
        <span>范围 {policyAppliesToLabel(policy.appliesTo)}</span>
        <span>{policyEnforcementModeLabel(policy.enforcementMode)}</span>
      </div>
    </div>
  );
}
