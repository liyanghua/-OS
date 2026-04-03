import Link from "next/link";
import type { CreativeVersion } from "@/domain/types";
import { creativeVersionStatusLabel } from "@/domain/mappers/display-zh";

type VisualVersionPoolRowProps = {
  version: CreativeVersion;
  projectNameLookup: Record<string, string>;
};

export function VisualVersionPoolRow({
  version,
  projectNameLookup,
}: VisualVersionPoolRowProps) {
  const name =
    projectNameLookup[version.projectId] ?? version.projectId;
  return (
    <div className="rounded-md border border-[var(--border)] px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium text-[var(--foreground)]">
          {version.name}
        </span>
        <span className="text-[var(--muted)]">
          {creativeVersionStatusLabel(version.status)}
        </span>
      </div>
      <div className="mt-1 text-[var(--muted)]">
        所属项目：
        <Link
          href={`/projects/${version.projectId}`}
          className="text-[var(--accent)] hover:underline"
        >
          {name}
        </Link>
      </div>
    </div>
  );
}
