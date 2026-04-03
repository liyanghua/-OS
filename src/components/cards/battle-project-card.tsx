import Link from "next/link";
import { LIFECYCLE_STAGE_LABELS } from "@/config/nav";
import type { ProjectObject } from "@/domain/types";
import {
  projectHealthLabel,
  riskLevelLabel,
} from "@/domain/mappers/display-zh";
import { battleProjectSurfaceClasses } from "@/domain/mappers/visual-surfaces";

type BattleProjectCardProps = {
  project: ProjectObject;
};

export function BattleProjectCard({ project }: BattleProjectCardProps) {
  const shell = battleProjectSurfaceClasses(project.health, project.riskLevel);
  return (
    <Link
      href={`/projects/${project.id}`}
      className={`block rounded-md border px-3 py-2.5 text-left text-sm transition-all duration-200 ${shell}`}
    >
      <div className="font-medium text-[var(--foreground)]">{project.name}</div>
      <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1 text-xs text-[var(--muted)]">
        <span>{LIFECYCLE_STAGE_LABELS[project.stage]}</span>
        <span>健康 {projectHealthLabel(project.health)}</span>
        <span>风险 {riskLevelLabel(project.riskLevel)}</span>
      </div>
      {project.targetSummary ? (
        <p className="mt-1 line-clamp-2 text-xs text-[var(--muted)]">
          {project.targetSummary}
        </p>
      ) : null}
    </Link>
  );
}
