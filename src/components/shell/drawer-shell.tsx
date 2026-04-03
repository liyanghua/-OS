"use client";

import type { ReactNode } from "react";

export type DrawerShellProps = {
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  /** 默认 max-w-md；详情可用 max-w-lg */
  maxWidthClass?: string;
};

export function DrawerShell({
  onClose,
  title,
  description,
  children,
  footer,
  maxWidthClass = "max-w-md",
}: DrawerShellProps) {
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <button
        type="button"
        className="absolute inset-0 bg-black/50"
        aria-label="关闭"
        onClick={onClose}
      />
      <aside
        className={`relative flex h-full w-full ${maxWidthClass} flex-col border-l border-[var(--border)] bg-gradient-to-b from-[var(--surface-elevated)] to-[var(--surface)] shadow-2xl shadow-black/40`}
      >
        <header className="shrink-0 border-b border-[var(--border)]/80 p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.04)]">
          <h2 className="text-lg font-semibold tracking-tight text-[var(--foreground)]">{title}</h2>
          {description ? (
            <p className="mt-1.5 text-sm text-[var(--muted)]">{description}</p>
          ) : null}
        </header>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-base">{children}</div>
        {footer != null ? (
          <footer className="shrink-0 border-t border-[var(--border)] p-4">{footer}</footer>
        ) : null}
      </aside>
    </div>
  );
}
