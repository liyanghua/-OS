"use client";

import type { RoleView } from "@/domain/types";
import { ROLE_LABELS } from "@/state/mock-projects";
import { useAppStore, useSetRoleView } from "@/state/app-store";

const ROLES: RoleView[] = [
  "ceo",
  "product_rd_director",
  "growth_director",
  "visual_director",
];

export function RoleSwitcher() {
  const { roleView } = useAppStore();
  const setRole = useSetRoleView();

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span className="mr-1 text-[11px] font-medium uppercase tracking-wider text-[var(--muted-2)]">
        当前视角
      </span>
      {ROLES.map((r) => (
        <button
          key={r}
          type="button"
          onClick={() => setRole(r)}
          className={`rounded-[var(--radius-md)] px-3 py-1.5 text-xs font-medium tracking-tight transition-[color,background-color,border-color,box-shadow] duration-150 ${
            roleView === r
              ? "bg-[var(--accent)] text-[var(--accent-foreground)] shadow-[inset_0_-1px_0_rgba(0,0,0,0.15)]"
              : "border border-[var(--border)] bg-[var(--surface)]/50 text-[var(--muted)] hover:border-[var(--accent)]/35 hover:bg-[var(--accent-muted)] hover:text-[var(--foreground)]"
          }`}
        >
          {ROLE_LABELS[r]}
        </button>
      ))}
    </div>
  );
}
