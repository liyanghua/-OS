import Link from "next/link";
import type { PublishedAsset } from "@/domain/types";
import { assetTypeLabel } from "@/domain/mappers/display-zh";

type VisualAssetRowProps = {
  asset: PublishedAsset;
  projectNameLookup: Record<string, string>;
};

export function VisualAssetRow({
  asset,
  projectNameLookup,
}: VisualAssetRowProps) {
  const projLabel = asset.sourceProjectId
    ? projectNameLookup[asset.sourceProjectId] ?? asset.sourceProjectId
    : "—";
  return (
    <div className="rounded-md border border-[var(--border)] px-3 py-2 text-xs">
      <div className="font-medium text-[var(--foreground)]">
        {asset.title}{" "}
        <span className="font-normal text-[var(--muted)]">
          （{assetTypeLabel(asset.type)}）
        </span>
      </div>
      <p className="mt-1 text-[var(--muted)]">{asset.summary}</p>
      {asset.sourceProjectId ? (
        <div className="mt-1">
          <Link
            href={`/projects/${asset.sourceProjectId}`}
            className="text-[var(--accent)] hover:underline"
          >
            来源：{projLabel}
          </Link>
        </div>
      ) : null}
    </div>
  );
}
