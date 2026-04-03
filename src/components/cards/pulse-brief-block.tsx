"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { PulseBundle } from "@/domain/types";
import {
  pulseCategoryLabel,
  riskLevelLabel,
  signalFreshnessLabel,
} from "@/domain/mappers/display-zh";
import { pulseItemSurfaceClasses } from "@/domain/mappers/visual-surfaces";
import { AiSignalFrame } from "@/components/cards/ai-signal-frame";
import { PulseIndicator } from "@/components/ui/pulse-indicator";

type PulseBriefBlockProps = {
  pulse: PulseBundle;
};

function formatGeneratedAt(iso: string): string {
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return iso;
  }
}

export function PulseBriefBlock({ pulse }: PulseBriefBlockProps) {
  const stats = useMemo(() => {
    const items = pulse.items;
    const riskSignal = items.filter(
      (i) =>
        i.category === "risk" || i.category === "blocker",
    ).length;
    const urgent = items.filter(
      (i) => i.severity === "high" || i.severity === "critical",
    ).length;
    const decisions = items.filter((i) => i.category === "approval").length;
    return { riskSignal, urgent, decisions };
  }, [pulse.items]);

  const headerTone =
    stats.urgent > 0 ? ("error" as const) : stats.riskSignal > 0 ? ("warning" as const) : ("live" as const);

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface)]/80 p-5 ring-1 ring-sky-500/10">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)]/45 pb-3">
        <div className="flex flex-wrap items-center gap-3">
          <PulseIndicator
            tone={headerTone === "error" ? "error" : headerTone === "warning" ? "warning" : "live"}
            label={headerTone === "live" ? "信号活跃" : headerTone === "warning" ? "需关注" : "严重项在列"}
          />
          <span className="text-base font-semibold tracking-tight text-[var(--foreground)] md:text-lg">
            经营脉冲
          </span>
        </div>
        <span className="font-mono-data text-xs text-[var(--muted)]">
          摘要更新时间 {formatGeneratedAt(pulse.generatedAt)}
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-12 lg:gap-5">
        <div className="lg:col-span-7">
          <AiSignalFrame
            label="经营大脑 · 今日摘要"
            footer={
              <span>
                三级呈现：上方摘要 → 右侧快扫指标 → 下方分项列表（原则 4.1）。
              </span>
            }
          >
            {pulse.summary}
          </AiSignalFrame>
        </div>
        <div className="grid grid-cols-3 gap-2 lg:col-span-5 lg:content-start">
          <div className="rounded-md border border-amber-500/25 bg-amber-500/[0.06] px-2.5 py-2 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-amber-100/95">
              高敏信号
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-[var(--foreground)]">
              {stats.urgent}
            </p>
          </div>
          <div className="rounded-md border border-sky-500/25 bg-sky-500/[0.06] px-2.5 py-2 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-sky-100/95">
              风险/阻塞
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-[var(--foreground)]">
              {stats.riskSignal}
            </p>
          </div>
          <div className="rounded-md border border-violet-500/25 bg-violet-500/[0.06] px-2.5 py-2 text-center">
            <p className="text-xs font-semibold uppercase tracking-wide text-violet-100/95">
              待决策
            </p>
            <p className="mt-1 text-2xl font-semibold tabular-nums tracking-tight text-[var(--foreground)]">
              {stats.decisions}
            </p>
          </div>
        </div>
      </div>

      <ul className="mt-4 space-y-2">
        {pulse.items.map((item) => (
          <li
            key={item.id}
            className={`rounded-md border px-3 py-2.5 text-sm transition-colors duration-200 hover:border-[var(--accent)]/35 ${pulseItemSurfaceClasses(item)}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-[var(--accent)]/15 px-1.5 py-0.5 font-medium text-[var(--accent)]">
                {pulseCategoryLabel(item.category)}
              </span>
              {item.severity ? (
                <span className="text-[var(--muted)]">
                  风险 {riskLevelLabel(item.severity)}
                </span>
              ) : null}
              <span className="text-[var(--muted)]">
                {signalFreshnessLabel(item.freshness)}
              </span>
            </div>
            <p className="mt-1.5 text-[var(--foreground)]">{item.summary}</p>
            {item.relatedProjectId ? (
              <p className="mt-1.5">
                <Link
                  href={`/projects/${item.relatedProjectId}`}
                  className="font-medium text-[var(--accent)] transition-colors hover:text-[var(--accent-hover)] hover:underline"
                >
                  进入商品项目详情 →
                </Link>
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
