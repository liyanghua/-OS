import type { ReactNode } from "react";

type ProvenanceRibbonVariant = "ai" | "pending" | "published";

const CLS: Record<ProvenanceRibbonVariant, string> = {
  ai: "border-[color-mix(in_srgb,amber_42%,transparent)] bg-[color-mix(in_srgb,amber_30%,transparent)] text-amber-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
  pending:
    "border-[color-mix(in_srgb,#fb923c_42%,transparent)] bg-[color-mix(in_srgb,#ea580c_26%,transparent)] text-orange-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
  published:
    "border-[color-mix(in_srgb,emerald_40%,transparent)] bg-[color-mix(in_srgb,emerald_32%,transparent)] text-emerald-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.06)]",
};

/** 深色管理台可读来源条（资产库 / 复盘共用） */
export function ProvenanceRibbon({
  variant,
  children,
}: {
  variant: ProvenanceRibbonVariant;
  children: ReactNode;
}) {
  return (
    <span
      className={`inline-flex rounded-md border px-2 py-0.5 text-[11px] font-semibold leading-tight ${CLS[variant]}`}
    >
      {children}
    </span>
  );
}
