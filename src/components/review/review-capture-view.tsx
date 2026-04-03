"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toReviewCaptureWorkspaceVm } from "@/domain/mappers/to-review-capture-workspace-vm";
import {
  approvalStatusLabel,
  assetPublishStatusLabel,
  assetTypeLabel,
  attributionCategoryLabel,
  reviewVerdictLabel,
  riskLevelLabel,
} from "@/domain/mappers/display-zh";
import { useAppStore } from "@/state/app-store";
import { ManagementPanel } from "@/components/cards/management-panel";
import { ProvenanceRibbon } from "@/components/cards/provenance-ribbon";
import { AiSignalFrame } from "@/components/cards/ai-signal-frame";
import { OperatingLayerLegendInline } from "@/components/cards/operating-layer-badge";
import { DrawerShell } from "@/components/shell/drawer-shell";
import type { AssetCandidate, ReviewToAssetVM } from "@/domain/types";

function candidatePipelineLabel(c: AssetCandidate): {
  variant: "ai" | "pending";
  text: string;
} {
  if (c.approvalStatus === "pending") {
    return { variant: "pending", text: "待人工确认" };
  }
  return { variant: "ai", text: "经营大脑 · 自动提炼草稿" };
}

/** 抽屉内：完整复盘与资产清单（与首屏摘要同源） */
function ReviewProjectFullBody({
  projectId,
  projectName,
  targetSummary,
  statusSummary,
  kpiSummary,
  chain,
}: {
  projectId: string;
  projectName: string;
  targetSummary: string;
  statusSummary: string;
  kpiSummary: string;
  chain: ReviewToAssetVM;
}) {
  const { review, assetCandidates, publishedAssets } = chain;
  const pendingHere = assetCandidates.filter((c) => c.approvalStatus === "pending");

  return (
    <div className="space-y-4 text-sm text-[var(--foreground)]">
      <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)]/60 pb-3">
        <span className="text-xs text-[var(--muted)]">项目 ID</span>
        <code className="rounded bg-[var(--border)]/20 px-1.5 text-xs">
          {projectId}
        </code>
        <Link
          href={`/projects/${projectId}`}
          className="text-xs font-medium text-[var(--accent)] hover:underline"
        >
          打开商品项目详情 →
        </Link>
      </div>

      <div className="rounded-md border border-[var(--border)]/70 bg-[var(--surface)]/90 p-3 text-xs">
        <p className="font-semibold text-[var(--foreground)]">复盘来源项目摘要</p>
        <p className="mt-1 text-[var(--muted)]">
          <span className="text-[var(--foreground)]">当前目标：</span>
          {targetSummary}
        </p>
        <p className="mt-1 text-[var(--muted)]">
          <span className="text-[var(--foreground)]">状态摘要：</span>
          {statusSummary}
        </p>
        <p className="mt-2 text-[var(--muted)]">
          <span className="text-[var(--foreground)]">关键指标结果：</span>
          {kpiSummary}
        </p>
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">结果复盘</h3>
          <ProvenanceRibbon variant="ai">经营大脑 · 结构化摘要</ProvenanceRibbon>
          <span className="rounded bg-[var(--border)]/30 px-2 py-0.5 text-xs">
            复盘结论：{reviewVerdictLabel(review.verdict)}
          </span>
        </div>
        <p className="mt-2 leading-relaxed text-[var(--muted)]">
          {review.resultSummary}
        </p>
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">原因归因</h3>
          <ProvenanceRibbon variant="ai">经营大脑 · 归因草稿</ProvenanceRibbon>
        </div>
        <p className="mt-2 text-[var(--muted)]">{review.attributionSummary}</p>
        {review.attributionFactors.length > 0 ? (
          <ul className="mt-3 space-y-2 border-l-2 border-[var(--accent)]/40 pl-3">
            {review.attributionFactors.map((f) => (
              <li key={f.id} className="text-xs">
                <span className="font-medium text-[var(--foreground)]">
                  {attributionCategoryLabel(f.category)}
                </span>
                <span className="text-[var(--muted)]"> · </span>
                <span>{f.summary}</span>
                <span className="ml-2 text-[var(--muted)]">
                  影响 {riskLevelLabel(f.impactLevel)} ·{" "}
                  {f.controllable ? "可控" : "外部/难控"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-[var(--muted)]">暂无结构化因素。</p>
        )}
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">经验总结</h3>
          <ProvenanceRibbon variant="pending">待沉淀为资产</ProvenanceRibbon>
        </div>
        {review.lessonsLearned.length > 0 ? (
          <ul className="mt-2 list-inside list-disc space-y-1 text-[var(--muted)]">
            {review.lessonsLearned.map((l, i) => (
              <li key={i}>{l}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-[var(--muted)]">暂无条目。</p>
        )}
      </div>

      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">可复用打法提炼</h3>
          <ProvenanceRibbon variant="pending">经营动作候选</ProvenanceRibbon>
        </div>
        {review.recommendations.length > 0 ? (
          <ul className="mt-2 list-inside list-decimal space-y-1 text-[var(--muted)]">
            {review.recommendations.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-xs text-[var(--muted)]">暂无打法条目。</p>
        )}
      </div>

      <div className="rounded-md border border-dashed border-[var(--border)] bg-[var(--surface)]/80 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">资产候选区</h3>
            <span className="text-xs text-[var(--muted)]">
              共 {assetCandidates.length} 条，待确认 {pendingHere.length} 条
            </span>
          </div>
          <Link
            href="/assets"
            className="text-xs font-medium text-[var(--accent)] hover:underline"
          >
            跳转经验资产库 →
          </Link>
        </div>
        {assetCandidates.length === 0 ? (
          <p className="mt-2 text-xs text-[var(--muted)]">暂无候选资产。</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {assetCandidates.map((c) => {
              const pipe = candidatePipelineLabel(c);
              return (
                <li
                  key={c.id}
                  className="flex flex-col gap-1 rounded-md border border-[var(--border)]/80 bg-[var(--surface)] p-2 sm:flex-row sm:items-start sm:justify-between"
                >
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs font-medium text-[var(--foreground)]">
                        {c.title}
                      </span>
                      <span className="rounded bg-[var(--border)]/25 px-1.5 text-[10px] text-[var(--muted)]">
                        {assetTypeLabel(c.type)}
                      </span>
                      <ProvenanceRibbon variant={pipe.variant}>
                        {pipe.text}
                      </ProvenanceRibbon>
                      <span className="text-[10px] text-[var(--muted)]">
                        {approvalStatusLabel(c.approvalStatus)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-[var(--muted)]">
                      {c.rationale}
                    </p>
                    {c.applicability ? (
                      <p className="mt-1 text-[10px] text-[var(--muted)]">
                        适用：{c.applicability}
                      </p>
                    ) : null}
                    <p className="mt-1 text-[10px] text-[var(--muted)]">
                      关联项目：
                      <Link
                        href={`/projects/${projectId}`}
                        className="text-[var(--accent)] hover:underline"
                      >
                        {projectName}
                      </Link>
                    </p>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div className="rounded-md border border-[var(--border)] bg-[var(--surface)]/80 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold">发布确认区</h3>
          <ProvenanceRibbon variant="published">已正式入库</ProvenanceRibbon>
        </div>
        <p className="mt-1 text-xs text-[var(--muted)]">
          以下条目已在组织资产库中；下线条目保留审计追溯。
        </p>
        {publishedAssets.length === 0 ? (
          <p className="mt-2 text-xs text-[var(--muted)]">
            本项目尚无已发布资产。
          </p>
        ) : (
          <ul className="mt-3 space-y-2">
            {publishedAssets.map((a) => (
              <li
                key={a.id}
                className="flex flex-col gap-1 rounded-md border border-[var(--border)]/80 p-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <span className="font-medium">{a.title}</span>
                  <span className="ml-2 text-xs text-[var(--muted)]">
                    {assetTypeLabel(a.type)}
                  </span>
                  <p className="mt-1 text-xs text-[var(--muted)]">{a.summary}</p>
                </div>
                <div className="flex flex-col items-start gap-1 sm:items-end">
                  <ProvenanceRibbon variant="published">
                    {assetPublishStatusLabel(a.status)}
                  </ProvenanceRibbon>
                  {a.reuseCount != null ? (
                    <span className="text-[10px] text-[var(--muted)]">
                      复用 {a.reuseCount} 次
                    </span>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ReviewProjectBlock({
  projectId,
  projectName,
  stageLabel,
  targetSummary,
  statusSummary,
  kpiSummary,
  chain,
}: {
  projectId: string;
  projectName: string;
  stageLabel: string;
  targetSummary: string;
  statusSummary: string;
  kpiSummary: string;
  chain: ReviewToAssetVM;
}) {
  const [fullOpen, setFullOpen] = useState(false);
  const { review, assetCandidates } = chain;
  const pendingHere = assetCandidates.filter((c) => c.approvalStatus === "pending");

  return (
    <>
      <ManagementPanel
        title={`${projectName}`}
        description={`来源阶段：${stageLabel} · 复盘—资产闭环（原型数据）`}
      >
        <div className="space-y-4 text-sm text-[var(--foreground)]">
          <div className="flex flex-wrap items-center gap-2 border-b border-[var(--border)]/60 pb-3">
            <span className="text-xs text-[var(--muted)]">项目 ID</span>
            <code className="font-mono-data rounded bg-[var(--border)]/20 px-1.5 text-xs">
              {projectId}
            </code>
            <Link
              href={`/projects/${projectId}`}
              className="text-xs font-medium text-[var(--accent)] hover:underline"
            >
              打开商品项目详情 →
            </Link>
          </div>

          <div className="rounded-md border border-[var(--border)]/70 bg-[var(--surface)]/90 p-3 text-xs">
            <p className="font-semibold text-[var(--foreground)]">复盘摘要（首屏）</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <ProvenanceRibbon variant="ai">经营大脑 · 结构化结论</ProvenanceRibbon>
              <span className="rounded bg-[var(--border)]/30 px-2 py-0.5 text-[11px]">
                复盘结论：{reviewVerdictLabel(review.verdict)}
              </span>
            </div>
            <p className="mt-2 leading-snug text-[var(--muted)]">
              <span className="font-medium text-[var(--foreground)]">关键指标结果：</span>
              {kpiSummary}
            </p>
            <p className="mt-2 text-[var(--muted)]">
              待人工确认资产候选{" "}
              <span className="font-semibold text-[var(--foreground)]">
                {pendingHere.length}
              </span>{" "}
              条
            </p>
            <div className="mt-2">
              <AiSignalFrame label="经营大脑 · 结果摘要（首屏预览）">
                <p className="line-clamp-3 text-[11px] leading-relaxed text-[var(--muted)]">
                  {review.resultSummary}
                </p>
              </AiSignalFrame>
            </div>
            <button
              type="button"
              className="mt-3 inline-flex items-center rounded-md border border-[var(--accent)]/50 bg-[var(--accent)]/15 px-3 py-2 text-xs font-semibold text-[var(--foreground)] hover:bg-[var(--accent)]/25"
              onClick={() => setFullOpen(true)}
            >
              展开完整复盘
            </button>
          </div>
        </div>
      </ManagementPanel>

      {fullOpen ? (
        <DrawerShell
          title={`完整复盘 · ${projectName}`}
          description="结果、归因、经验、打法与资产清单。"
          maxWidthClass="max-w-lg"
          onClose={() => setFullOpen(false)}
        >
          <ReviewProjectFullBody
            projectId={projectId}
            projectName={projectName}
            targetSummary={targetSummary}
            statusSummary={statusSummary}
            kpiSummary={kpiSummary}
            chain={chain}
          />
        </DrawerShell>
      ) : null}
    </>
  );
}

export function ReviewCaptureView() {
  const searchParams = useSearchParams();
  const filterProjectId = searchParams.get("projectId") ?? undefined;

  const { projects } = useAppStore();
  const vm = useMemo(() => toReviewCaptureWorkspaceVm(projects), [projects]);

  const displayBlocks = useMemo(() => {
    if (!filterProjectId) return vm.blocks;
    return vm.blocks.filter((b) => b.projectId === filterProjectId);
  }, [vm.blocks, filterProjectId]);

  const scopedPublished = useMemo(
    () => displayBlocks.flatMap((b) => b.chain.publishedAssets),
    [displayBlocks],
  );
  const scopedPendingCandidates = useMemo(
    () =>
      displayBlocks.flatMap((b) => b.chain.assetCandidates).filter(
        (c) => c.approvalStatus === "pending",
      ),
    [displayBlocks],
  );
  const aiFastTrackCandidates = useMemo(() => {
    return displayBlocks
      .flatMap((b) => b.chain.assetCandidates)
      .filter((c) => c.approvalStatus !== "pending").length;
  }, [displayBlocks]);

  const filterProjectMeta = useMemo(() => {
    if (!filterProjectId) return null;
    return projects.find((p) => p.id === filterProjectId) ?? null;
  }, [projects, filterProjectId]);

  const filterMissingReview =
    Boolean(filterProjectId) && displayBlocks.length === 0;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="app-page-title">
          复盘沉淀台
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-[var(--muted)]">
          复盘不是结束：把「结果—归因—经验—打法」结构化为资产候选，再经人工确认发布到组织经验资产库，形成学习闭环。结构化内容由经营大脑输出，入库前由人工节点确认。
        </p>
        <div className="mt-3 rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--surface-elevated)]/50 p-3 ring-1 ring-white/[0.04]">
          <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-[var(--muted)]">
            与其他页面一致的四层协同语言
          </p>
          <OperatingLayerLegendInline />
        </div>
      </header>

      {filterProjectId ? (
        <div className="rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-3 text-sm">
          {filterMissingReview ? (
            <>
              <p className="text-[var(--foreground)]">
                深链项目{" "}
                <code className="rounded bg-[var(--border)]/25 px-1">
                  {filterProjectId}
                </code>{" "}
                在 mock 中无复盘摘要，已无法收窄块列表。
              </p>
              {filterProjectMeta ? (
                <p className="mt-1 text-xs text-[var(--muted)]">
                  可回到商品项目页继续推进经营动作后再试。
                </p>
              ) : null}
            </>
          ) : (
            <p className="font-medium text-[var(--foreground)]">
              单项目视图：{displayBlocks[0]?.projectName ?? filterProjectId}
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-3 text-xs">
            {filterProjectMeta ? (
              <Link
                href={`/projects/${filterProjectMeta.id}`}
                className="text-[var(--accent)] hover:underline"
              >
                打开商品项目详情
              </Link>
            ) : null}
            <Link href="/lifecycle/review-capture" className="text-[var(--accent)] hover:underline">
              查看全部复盘项目
            </Link>
          </div>
        </div>
      ) : null}

      <ManagementPanel
        title="闭环状态一览"
        description="三类内容在产品上必须可分：经营大脑结构化提炼、待人工确认、已正式入库。"
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3">
            <p className="text-xs font-medium text-[var(--foreground)]">
              经营大脑 · 结构化提炼
            </p>
            <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">
              {displayBlocks.length}
            </p>
            <p className="text-xs text-[var(--muted)]">
              份结构化复盘摘要（当前视图按项目{filterProjectId ? "收窄" : "全库"}）；另有 {aiFastTrackCandidates}{" "}
              条候选由经营大脑快速成稿（审批：{approvalStatusLabel("not_required")}）
            </p>
          </div>
          <div className="rounded-md border border-orange-500/30 bg-orange-500/5 p-3">
            <p className="text-xs font-medium text-[var(--foreground)]">
              待人工确认
            </p>
            <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">
              {scopedPendingCandidates.length}
            </p>
            <p className="text-xs text-[var(--muted)]">
              条资产候选需人工确认后入库
            </p>
          </div>
          <div className="rounded-md border border-emerald-500/30 bg-emerald-500/5 p-3">
            <p className="text-xs font-medium text-[var(--foreground)]">
              已正式入库
            </p>
            <p className="mt-1 text-2xl font-semibold text-[var(--foreground)]">
              {scopedPublished.filter((a) => a.status === "published").length}
            </p>
            <p className="text-xs text-[var(--muted)]">
              条已发布资产（当前视图共 {scopedPublished.length} 条含草稿/下线）
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs text-[var(--muted)]">
          数据来自{" "}
          <code className="rounded bg-[var(--border)]/25 px-1">ReviewSummary</code>、
          <code className="rounded bg-[var(--border)]/25 px-1">
            AttributionFactor[]
          </code>、
          <code className="rounded bg-[var(--border)]/25 px-1">
            AssetCandidate[]
          </code>、
          <code className="rounded bg-[var(--border)]/25 px-1">
            PublishedAsset[]
          </code>{" "}
          的聚合映射（mock）。
        </p>
      </ManagementPanel>

      {vm.blocks.length === 0 ? (
        <ManagementPanel title="暂无复盘项目" description="当前 mock 中无含复盘摘要的项目。">
          <p className="text-sm text-[var(--muted)]">请在项目中补齐 review 字段后查看。</p>
        </ManagementPanel>
      ) : filterMissingReview ? null : (
        <div className="space-y-6">
          {displayBlocks.map((b) => (
            <ReviewProjectBlock key={b.projectId} {...b} />
          ))}
        </div>
      )}
    </div>
  );
}
