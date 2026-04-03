"use client";

import { WalkthroughHintPanel } from "@/components/shell/walkthrough-hint-panel";
import Link from "next/link";
import { useMemo } from "react";
import { toVisualDirectorVm } from "@/domain/mappers/to-visual-vm";
import {
  expressionReadinessLabel,
  projectHealthLabel,
  riskLevelLabel,
} from "@/domain/mappers/display-zh";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { PulseBriefBlock } from "@/components/cards/pulse-brief-block";
import { BattleProjectCard } from "@/components/cards/battle-project-card";
import { VisualVersionPoolRow } from "@/components/cards/visual-version-pool-row";
import { VisualAssetRow } from "@/components/cards/visual-asset-row";

export function VisualDirectorView() {
  const { projects, exceptions } = useAppStore();
  const vm = useMemo(
    () => toVisualDirectorVm(projects, exceptions),
    [projects, exceptions],
  );

  const projectNameById = useMemo(
    () => Object.fromEntries(projects.map((p) => [p.id, p.name])),
    [projects],
  );

  const newExpressionReady = useMemo(
    () =>
      vm.expressionProjects.filter(
        (p) =>
          p.stage === "new_product_incubation" &&
          p.expression &&
          (p.expression.readinessStatus === "in_progress" ||
            p.expression.readinessStatus === "not_started"),
      ),
    [vm.expressionProjects],
  );

  const poolPreview = useMemo(
    () => vm.creativeVersionPool.slice(0, 12),
    [vm.creativeVersionPool],
  );

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          视觉总监工作台
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          表达脉冲与版本池：关注新品表达准备、主视觉对比、老品焕新与可复用模板（已发布资产）。
        </p>
      </header>

      <WalkthroughHintPanel variant="visual" />

      <ManagementPanel
        title="表达脉冲"
        description="与表达规划、视觉迭代相关的信号（视角加权）。"
      >
        <PulseBriefBlock pulse={vm.pulse} />
      </ManagementPanel>

      <ManagementPanel
        title="新品表达准备"
        description="孵化阶段且表达就绪尚未完成的重点条目。"
      >
        {newExpressionReady.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">
            暂无「孵化中且表达未就绪」的突出项。
          </p>
        ) : (
          <ul className="space-y-2 text-xs">
            {newExpressionReady.map((p) => (
              <li
                key={p.id}
                className="rounded-md border border-[var(--border)] px-3 py-2"
              >
                <Link
                  href={`/projects/${p.id}`}
                  className="font-medium text-[var(--accent)] hover:underline"
                >
                  {p.name}
                </Link>
                {p.expression ? (
                  <div className="mt-1 text-[var(--muted)]">
                    表达就绪 {expressionReadinessLabel(p.expression.readinessStatus)}
                    · 健康 {projectHealthLabel(p.health)} · 风险{" "}
                    {riskLevelLabel(p.riskLevel)}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="视觉版本对比池"
        description="跨项目聚合的创意版本（原型列表，截断展示）。"
      >
        {poolPreview.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无创意版本数据。</p>
        ) : (
          <div className="space-y-2">
            {poolPreview.map((v) => (
              <VisualVersionPoolRow
                key={v.id}
                version={v}
                projectNameLookup={projectNameById}
              />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="老品视觉升级"
        description="老品升级且已挂表达规划的项目。"
      >
        {vm.upgradeCandidates.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">
            暂无老品视觉升级候选。
          </p>
        ) : (
          <div className="grid gap-2 sm:grid-cols-2">
            {vm.upgradeCandidates.map((p) => (
              <BattleProjectCard key={p.id} project={p} />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="模板与复用资产"
        description="已发布、可复用的经验资产摘要（按项目聚合）。"
      >
        {vm.reusableAssets.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无已发布资产。</p>
        ) : (
          <div className="space-y-2">
            {vm.reusableAssets.map((a) => (
              <VisualAssetRow
                key={a.id}
                asset={a}
                projectNameLookup={projectNameById}
              />
            ))}
          </div>
        )}
      </ManagementPanel>

      <ManagementPanel
        title="表达规划覆盖（阶段）"
        description="各重点阶段下挂有表达规划的商品项目一览。"
      >
        {vm.expressionProjects.length === 0 ? (
          <p className="text-xs text-[var(--muted)]">暂无表达规划项目。</p>
        ) : (
          <ul className="space-y-1 text-xs text-[var(--muted)]">
            {vm.expressionProjects.map((p) => (
              <li key={p.id}>
                <Link
                  href={`/projects/${p.id}`}
                  className="text-[var(--accent)] hover:underline"
                >
                  {p.name}
                </Link>
                {" · "}
                {LIFECYCLE_STAGE_LABELS[p.stage]}
                {p.expression
                  ? ` · ${expressionReadinessLabel(p.expression.readinessStatus)}`
                  : ""}
              </li>
            ))}
          </ul>
        )}
      </ManagementPanel>
    </div>
  );
}
