import type {
  CreativeVersion,
  ExceptionItem,
  LifecycleStage,
  ProjectObject,
  PublishedAsset,
  VisualDirectorVM,
} from "@/domain/types";
import { buildPulseBundleForRole } from "@/domain/mappers/pulse-shared";

const EXPRESSION_FOCUS_STAGES: LifecycleStage[] = [
  "new_product_incubation",
  "launch_validation",
  "growth_optimization",
  "legacy_upgrade",
];

function collectCreativeVersionPool(projects: ProjectObject[]): CreativeVersion[] {
  const pool: CreativeVersion[] = [];
  const seen = new Set<string>();
  for (const p of projects) {
    for (const cv of p.expression?.creativeVersions ?? []) {
      if (!seen.has(cv.id)) {
        seen.add(cv.id);
        pool.push(cv);
      }
    }
  }
  return pool.sort((a, b) => {
    const order = (s: CreativeVersion["status"]) =>
      s === "testing" ? 0 : s === "draft" ? 1 : s === "selected" ? 2 : 3;
    return order(a.status) - order(b.status);
  });
}

function collectReusableAssets(projects: ProjectObject[]): PublishedAsset[] {
  const out: PublishedAsset[] = [];
  const seen = new Set<string>();
  for (const p of projects) {
    for (const asset of p.publishedAssets ?? []) {
      if (!seen.has(asset.id)) {
        seen.add(asset.id);
        out.push(asset);
      }
    }
  }
  return out;
}

export function toVisualDirectorVm(
  projects: ProjectObject[],
  exceptions: ExceptionItem[],
): VisualDirectorVM {
  const pulse = buildPulseBundleForRole("visual_director", projects, exceptions);

  const expressionProjects = projects.filter(
    (p) => p.expression != null && EXPRESSION_FOCUS_STAGES.includes(p.stage),
  );

  const creativeVersionPool = collectCreativeVersionPool(projects);

  const upgradeCandidates = projects.filter(
    (p) => p.stage === "legacy_upgrade" && p.expression != null,
  );

  const reusableAssets = collectReusableAssets(projects);

  return {
    pulse,
    expressionProjects,
    creativeVersionPool,
    upgradeCandidates,
    reusableAssets,
  };
}
