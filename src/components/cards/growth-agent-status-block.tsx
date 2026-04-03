import Link from "next/link";
import type { AgentState, ProjectObject } from "@/domain/types";
import { agentStatusLabel } from "@/domain/mappers/display-zh";
import { AgentStatusIndicator } from "@/components/ui/agent-status-indicator";

function collectAgents(
  launchProjects: ProjectObject[],
  optimizationProjects: ProjectObject[],
): { state: AgentState; projectName: string; projectId: string }[] {
  const out: { state: AgentState; projectName: string; projectId: string }[] =
    [];
  for (const p of [...launchProjects, ...optimizationProjects]) {
    for (const s of p.agentStates) {
      out.push({ state: s, projectName: p.name, projectId: p.id });
    }
  }
  return out;
}

type GrowthAgentStatusBlockProps = {
  launchProjects: ProjectObject[];
  optimizationProjects: ProjectObject[];
};

export function GrowthAgentStatusBlock({
  launchProjects,
  optimizationProjects,
}: GrowthAgentStatusBlockProps) {
  const rows = collectAgents(launchProjects, optimizationProjects);
  if (rows.length === 0) {
    return (
      <p className="text-xs text-[var(--muted)]">
        首发与增长战线中暂无智能体状态（原型，后续可接实时编排）。
      </p>
    );
  }

  return (
    <ul className="space-y-2">
      {rows.map(({ state, projectName, projectId }) => (
        <li
          key={state.id}
          className="rounded-md border border-[var(--border)] px-3 py-2.5 text-sm transition-colors duration-200 hover:border-[var(--accent)]/25"
        >
          <div className="flex flex-wrap items-center gap-2">
            <AgentStatusIndicator status={state.status} />
            <span className="font-semibold text-[var(--foreground)]">
              {agentStatusLabel(state.status)}
            </span>
            <Link
              href={`/projects/${projectId}`}
              className="text-[var(--accent)] hover:underline"
            >
              {projectName}
            </Link>
          </div>
          <p className="mt-1.5 text-sm leading-relaxed text-[var(--muted)]">
            {state.summary}
          </p>
        </li>
      ))}
    </ul>
  );
}
