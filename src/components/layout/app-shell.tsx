"use client";

import type { ReactNode } from "react";
import { SideNav } from "./side-nav";
import { RoleSwitcher } from "./role-switcher";
import { OperatingContextStrip } from "./operating-context-strip";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen">
      <SideNav />
      <div className="flex min-w-0 flex-1 flex-col border-l border-[var(--border-subtle)]">
        <header
          className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] bg-[var(--surface-elevated)]/92 px-6 py-3.5 backdrop-blur-md"
          style={{ boxShadow: "var(--shadow-header)" }}
        >
          <RoleSwitcher />
          <p className="max-w-md text-xs leading-relaxed tracking-tight text-[var(--muted)]">
            例外优先的经营界面：突出待审批、风险与阻塞问题；不做普通任务清单，不提供全局悬浮聊天。
          </p>
        </header>
        <OperatingContextStrip />
        <main className="app-workspace flex-1 overflow-auto px-6 py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
