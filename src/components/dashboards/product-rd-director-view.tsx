"use client";

import { WalkthroughHintPanel } from "@/components/shell/walkthrough-hint-panel";
import Link from "next/link";
import { useMemo } from "react";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import { toProductRdDirectorVm } from "@/domain/mappers/to-product-rd-vm";
import {
  projectHealthLabel,
  riskLevelLabel,
  samplingStatusLabel,
} from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";

export function ProductRdDirectorView() {
  const { projects, exceptions } = useAppStore();
  const vm = useMemo(
    () => toProductRdDirectorVm(projects, exceptions),
    [projects, exceptions],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          产品研发总监工作台
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          以商机与孵化为轴：先看脉冲，再分布商机池与新品进度，聚焦定义与打样风险及老品升级机会。数据来自当前
          mock。
        </p>
      </header>

      <WalkthroughHintPanel variant="product_rd" />

      <ManagementPanel
        title="商机脉冲"
        description="与商机池、孵化阶段相关的经营信号（视角加权）。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="商机池摘要"
        description="当前处于商机池阶段的商品项目。"
      >
        {vm.opportunityProjects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无商机池项目。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.opportunityProjects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="新品孵化进度"
        description="新品孵化阶段项目在盘。"
      >
        {vm.incubationProjects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无孵化中项目。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.incubationProjects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="商品定义与打样风险"
        description="按可行性风险与打样状态排序的风险候选（原型）。"
      >
        {vm.topSamplingRisks.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无带商品定义的风险条目。</p>
        ) : (
          <ul className="space-y-2">
            {vm.topSamplingRisks.map((p) => (
              <li
                key={p.id}
                className="rounded-md border border-[var(--border)] px-3 py-2 text-xs"
              >
                <div className="font-medium text-[var(--foreground)]">
                  <Link
                    href={`/projects/${p.id}`}
                    className="hover:text-[var(--accent)]"
                  >
                    {p.name}
                  </Link>
                </div>
                {p.definition ? (
                  <div className="mt-1 space-y-0.5 text-[var(--muted)]">
                    <div>
                      可行性风险 {riskLevelLabel(p.definition.feasibilityRisk)}
                    </div>
                    <div>
                      打样 {samplingStatusLabel(p.definition.samplingStatus)}
                    </div>
                    <div>
                      健康 {projectHealthLabel(p.health)} · 阶段{" "}
                      {LIFECYCLE_STAGE_LABELS[p.stage]}
                    </div>
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="老品升级机会"
        description="老品升级阶段项目。"
      >
        {vm.upgradeProjects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无老品升级项目。</p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.upgradeProjects.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>
    </div>
  );
}
