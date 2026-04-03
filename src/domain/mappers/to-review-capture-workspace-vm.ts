import type { ProjectObject, ReviewCaptureWorkspaceVM } from "@/domain/types";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";

function formatKpiSummary(project: ProjectObject): string {
  const m = project.kpis.metrics;
  if (m.length === 0) return "暂无 KPI 快照";
  return m
    .map((x) => `${x.label} ${x.value}${x.unit ? x.unit : ""}`)
    .join(" · ");
}

export function toReviewCaptureWorkspaceVm(
  projects: ProjectObject[],
): ReviewCaptureWorkspaceVM {
  const withReviewFiltered = projects.filter((p) => p.review != null);
  const sorted = [...withReviewFiltered].sort((a, b) => {
    const ar = a.stage === "review_capture" ? 0 : 1;
    const br = b.stage === "review_capture" ? 0 : 1;
    if (ar !== br) return ar - br;
    return a.name.localeCompare(b.name, "zh-CN");
  });

  const blocks = sorted.map((p) => ({
    projectId: p.id,
    projectName: p.name,
    stageLabel: LIFECYCLE_STAGE_LABELS[p.stage],
    targetSummary: p.targetSummary,
    statusSummary: p.statusSummary,
    kpiSummary: formatKpiSummary(p),
    chain: {
      review: p.review!,
      assetCandidates: p.assetCandidates ?? [],
      publishedAssets: p.publishedAssets ?? [],
    },
  }));

  const allPendingCandidates = projects
    .flatMap((p) => p.assetCandidates ?? [])
    .filter((c) => c.approvalStatus === "pending");

  const allPublishedAssets = projects.flatMap(
    (p) => p.publishedAssets ?? [],
  );

  return {
    blocks,
    allPendingCandidates,
    allPublishedAssets,
  };
}
