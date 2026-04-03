"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  ASSET_HUB_TYPE_ORDER,
  toAssetHubVm,
} from "@/domain/mappers/to-asset-hub-vm";
import {
  approvalStatusLabel,
  assetPublishStatusLabel,
  assetTypeLabel,
} from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { ProvenanceRibbon } from "@/components/cards/provenance-ribbon";
import type { AssetCandidate, PublishedAsset } from "@/domain/types";

function candidateRibbon(c: AssetCandidate) {
  if (c.approvalStatus === "pending") {
    return (
      <ProvenanceRibbon variant="pending">待人工确认</ProvenanceRibbon>
    );
  }
  return (
    <ProvenanceRibbon variant="ai">经营大脑 · 自动提炼</ProvenanceRibbon>
  );
}

function PublishedAssetCard({ a, projectNames }: { a: PublishedAsset; projectNames: Map<string, string> }) {
  const src =
    a.sourceProjectId != null
      ? projectNames.get(a.sourceProjectId) ?? a.sourceProjectId
      : null;
  return (
    <li className="rounded-md border border-[var(--border)]/80 bg-[var(--surface)] p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-[var(--foreground)]">{a.title}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">{a.summary}</p>
          {src ? (
            <p className="mt-2 text-[10px] text-[var(--muted)]">
              来源项目：{src}
            </p>
          ) : null}
        </div>
        <div className="flex flex-col items-end gap-1">
          <ProvenanceRibbon variant="published">
            {`${assetPublishStatusLabel(a.status)} · 正式入库`}
          </ProvenanceRibbon>
          {a.reuseCount != null ? (
            <span className="text-[10px] text-[var(--muted)]">
              复用 {a.reuseCount} 次
            </span>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function CandidateAssetCard({
  c,
  projectNames,
}: {
  c: AssetCandidate;
  projectNames: Map<string, string>;
}) {
  const pn = projectNames.get(c.projectId) ?? c.projectId;
  return (
    <li className="rounded-md border border-dashed border-[var(--border)] bg-[var(--surface)]/90 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-medium text-[var(--foreground)]">{c.title}</p>
          <p className="mt-1 text-xs text-[var(--muted)]">{c.rationale}</p>
          <p className="mt-2 text-[10px] text-[var(--muted)]">
            来源项目：{pn} · {approvalStatusLabel(c.approvalStatus)}
          </p>
        </div>
        {candidateRibbon(c)}
      </div>
    </li>
  );
}

export function AssetHubView() {
  const { projects } = useAppStore();
  const vm = useMemo(() => toAssetHubVm(projects), [projects]);
  const projectNames = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of projects) m.set(p.id, p.name);
    return m;
  }, [projects]);

  const pendingTotal = vm.candidatesAll.filter(
    (c) => c.approvalStatus === "pending",
  ).length;
  const publishedTotal = vm.publishedAll.filter(
    (a) => a.status === "published",
  ).length;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          经验资产库
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          组织级可复用经营物料：按类型分区展示「已入库」与「候选」，强调复盘闭环产出而非网盘式堆叠。
        </p>
      </header>

      <ManagementPanel
        title="库内结构"
        description="六类资产 + 候选池；与复盘沉淀台共用同一套领域类型。"
      >
        <div className="flex flex-wrap gap-3 text-xs text-[var(--muted)]">
          <span>
            已发布{" "}
            <strong className="text-[var(--foreground)]">{publishedTotal}</strong>{" "}
            条
          </span>
          <span>
            候选{" "}
            <strong className="text-[var(--foreground)]">
              {vm.candidatesAll.length}
            </strong>{" "}
            条（待确认 {pendingTotal}）
          </span>
          <Link
            href="/lifecycle/review-capture"
            className="font-medium text-[var(--accent)] hover:underline"
          >
            ← 回到复盘沉淀台
          </Link>
        </div>
      </ManagementPanel>

      <div className="space-y-6">
        {ASSET_HUB_TYPE_ORDER.map((type) => {
          const published = vm.publishedByType[type];
          const candidates = vm.candidatesByType[type];
          if (published.length === 0 && candidates.length === 0) {
            return (
              <ManagementPanel
                key={type}
                title={assetTypeLabel(type)}
                description="本类型暂无条目（mock 可按里程碑继续补种）。"
              >
                <p className="text-xs text-[var(--muted)]">占位：等待数据补齐。</p>
              </ManagementPanel>
            );
          }
          return (
            <ManagementPanel
              key={type}
              title={assetTypeLabel(type)}
              description={`已入库 ${published.length} · 候选 ${candidates.length}`}
            >
              <div className="grid gap-4 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-[var(--foreground)]">
                    已正式入库
                    <ProvenanceRibbon variant="published">可复用</ProvenanceRibbon>
                  </h3>
                  {published.length === 0 ? (
                    <p className="text-xs text-[var(--muted)]">暂无。</p>
                  ) : (
                    <ul className="space-y-2">
                      {published.map((a) => (
                        <PublishedAssetCard
                          key={a.id}
                          a={a}
                          projectNames={projectNames}
                        />
                      ))}
                    </ul>
                  )}
                </div>
                <div>
                  <h3 className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-[var(--foreground)]">
                    候选资产
                    <ProvenanceRibbon variant="pending">待沉淀</ProvenanceRibbon>
                  </h3>
                  {candidates.length === 0 ? (
                    <p className="text-xs text-[var(--muted)]">暂无候选。</p>
                  ) : (
                    <ul className="space-y-2">
                      {candidates.map((c) => (
                        <CandidateAssetCard
                          key={c.id}
                          c={c}
                          projectNames={projectNames}
                        />
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            </ManagementPanel>
          );
        })}
      </div>
    </div>
  );
}
