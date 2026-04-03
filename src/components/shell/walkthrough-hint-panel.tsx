"use client";

import { useState } from "react";

export type WalkthroughHintVariant = "ceo" | "growth" | "product_rd" | "visual";

const COPY: Record<
  WalkthroughHintVariant,
  { look: string; handle: string; next: string }
> = {
  ceo: {
    look: "优先看「经营脉冲」里的高风险/阻塞与「重点风险与待审批」中的例外摘要。",
    handle: "最值得先收口：需您拍板的待审批与需人工介入的例外；再下钻关键战役项目卡片。",
    next: "建议下一步打开商品经营主线总览看阶段分布，或进入动作中心做待批闭环。",
  },
  growth: {
    look: "优先看「增长脉冲」与首发/增长项目分区里的健康与风险标签。",
    handle: "最值得先处理：待审批动作列表与阻塞地图中排序靠前的高严重度项。",
    next: "建议下一步进入对应阶段工作台（首发验证 / 增长优化），或从脉冲项链到商品项目详情现场走查。",
  },
  product_rd: {
    look: "优先看「商机脉冲」与新品孵化 / 商机池项目卡片。",
    handle: "最值得先盯：商品定义与打样风险列表中可行性与打样状态偏高的条目。",
    next: "建议下一步打开新品孵化阶段页，或对风险候选直接进入项目详情。",
  },
  visual: {
    look: "优先看「表达脉冲」与新品表达准备、视觉版本对比池。",
    handle: "最值得先对齐：表达未就绪的孵化项目与版本池中的测试/待选物料。",
    next: "建议下一步从版本行或项目行进入项目详情核对表达规划与创意版本。",
  },
};

type WalkthroughHintPanelProps = {
  variant: WalkthroughHintVariant;
  /** 为 true 时首屏仅显示折叠条，展开后出现完整走查文案 */
  defaultCollapsed?: boolean;
};

/** 走查辅助（非正式 onboarding） */
export function WalkthroughHintPanel({
  variant,
  defaultCollapsed = false,
}: WalkthroughHintPanelProps) {
  const [open, setOpen] = useState(!defaultCollapsed);
  const c = COPY[variant];

  return (
    <section
      className="panel-top-sheen relative overflow-hidden rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface)] p-5 ring-1 ring-white/[0.035]"
      style={{ boxShadow: "var(--shadow-card)" }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-[var(--border)]/50 pb-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-lg font-semibold leading-snug tracking-tight text-[var(--foreground)] md:text-xl">
            走查提示（辅助）
          </h2>
          {open ? (
            <p className="mt-1.5 max-w-4xl text-sm leading-relaxed text-[var(--muted)]">
              仅作走查备忘：谁先读、先处理什么、建议切到哪一页；非强制引导流程。
            </p>
          ) : (
            <p className="mt-1.5 text-sm text-[var(--muted)]">
              已折叠：首屏优先脉冲与主动作；需要时点右侧展开。
            </p>
          )}
        </div>
        <button
          type="button"
          className="shrink-0 rounded-md border border-[var(--border)] bg-[var(--surface-elevated)]/50 px-2.5 py-1 text-[11px] font-medium text-[var(--foreground)] hover:bg-[var(--border)]/20"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "收起" : "展开走查"}
        </button>
      </div>
      {open ? (
        <ul className="mt-4 list-inside list-decimal space-y-2 text-sm text-[var(--muted)]">
          <li>
            <span className="font-medium text-[var(--foreground)]">应先看什么：</span>
            {c.look}
          </li>
          <li>
            <span className="font-medium text-[var(--foreground)]">当前最值得处理：</span>
            {c.handle}
          </li>
          <li>
            <span className="font-medium text-[var(--foreground)]">下一步建议：</span>
            {c.next}
          </li>
        </ul>
      ) : null}
    </section>
  );
}
