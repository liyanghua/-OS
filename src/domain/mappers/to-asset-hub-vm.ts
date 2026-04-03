import type {
  AssetCandidate,
  AssetHubVM,
  AssetType,
  ProjectObject,
  PublishedAsset,
} from "@/domain/types";

/** 经验资产库类型分区顺序（与 IMPLEMENT / 产品表述一致） */
export const ASSET_HUB_TYPE_ORDER: AssetType[] = [
  "case",
  "rule",
  "template",
  "skill",
  "sop",
  "evaluation_sample",
];

function emptyPublishedByType(): Record<AssetType, PublishedAsset[]> {
  const r = {} as Record<AssetType, PublishedAsset[]>;
  for (const t of ASSET_HUB_TYPE_ORDER) r[t] = [];
  return r;
}

function emptyCandidatesByType(): Record<AssetType, AssetCandidate[]> {
  const r = {} as Record<AssetType, AssetCandidate[]>;
  for (const t of ASSET_HUB_TYPE_ORDER) r[t] = [];
  return r;
}

export function toAssetHubVm(projects: ProjectObject[]): AssetHubVM {
  const publishedAll = projects.flatMap((p) => p.publishedAssets ?? []);
  const candidatesAll = projects.flatMap((p) => p.assetCandidates ?? []);

  const publishedByType = emptyPublishedByType();
  for (const a of publishedAll) {
    publishedByType[a.type].push(a);
  }

  const candidatesByType = emptyCandidatesByType();
  for (const c of candidatesAll) {
    candidatesByType[c.type].push(c);
  }

  return {
    publishedByType,
    candidatesByType,
    publishedAll,
    candidatesAll,
  };
}
