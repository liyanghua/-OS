import Link from "next/link";
import type { ProjectObject } from "@/domain/types";
import { filterPlanCompareCandidates } from "@/domain/selectors/plan-compare-candidates";

/** 任意项目列表内：多决策选项或多视觉版本 */
export function planCompareProjectsInList(
  projects: ProjectObject[],
): ProjectObject[] {
  return filterPlanCompareCandidates(projects);
}

export function planCompareProjects(
  launchProjects: ProjectObject[],
  optimizationProjects: ProjectObject[],
): ProjectObject[] {
  return filterPlanCompareCandidates([...launchProjects, ...optimizationProjects]);
}

type GrowthPlanCompareBlockProps = {
  projects: ProjectObject[];
};

export function GrowthPlanCompareBlock({
  projects,
}: GrowthPlanCompareBlockProps) {
  if (projects.length === 0) {
    return (
      <p className="text-xs text-[var(--muted)]">
        暂无可对比的多方案条目（原型：需决策多选项或多视觉版本并存）。
      </p>
    );
  }

  return (
    <ul className="space-y-3">
      {projects.map((p) => {
        const opts = p.decisionObject?.options ?? [];
        const vers = p.expression?.creativeVersions ?? [];
        return (
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
            {opts.length >= 2 ? (
              <div className="mt-1.5 text-[var(--muted)]">
                <span className="text-[var(--foreground)]">经营方案对比：</span>
                {opts.map((o) => o.title).join(" · ")}
              </div>
            ) : null}
            {vers.length >= 2 ? (
              <div className="mt-1 text-[var(--muted)]">
                <span className="text-[var(--foreground)]">视觉版本对比：</span>
                {vers.map((v) => v.name).join(" · ")}
              </div>
            ) : null}
          </li>
        );
      })}
    </ul>
  );
}
