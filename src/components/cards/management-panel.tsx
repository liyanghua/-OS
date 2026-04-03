import type { ReactNode } from "react";

type ManagementPanelProps = {
  title: string;
  description?: string;
  children?: ReactNode;
  /** 供动作中心 progress rail 锚点滚动 */
  id?: string;
};

export function ManagementPanel({
  title,
  description,
  children,
  id,
}: ManagementPanelProps) {
  return (
    <section
      id={id}
      className="panel-top-sheen relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface)] p-5 ring-1 ring-white/[0.035] scroll-mt-6"
      style={{ boxShadow: "var(--shadow-card)" }}
    >
      <div className="border-b border-[var(--border)]/45 pb-3">
        <h2 className="text-lg font-semibold leading-snug tracking-tight text-[var(--foreground)] md:text-xl">
          {title}
        </h2>
        {description ? (
          <p className="mt-2 max-w-4xl text-sm leading-relaxed text-[var(--muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {children ? <div className="mt-4 space-y-2">{children}</div> : null}
    </section>
  );
}
