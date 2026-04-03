import Link from "next/link";
import type { AgentState, ProjectObject } from "@/domain/types";
import { agentStatusLabel } from "@/domain/mappers/display-zh";
import { AgentStatusIndicator } from "@/components/ui/agent-status-indicator";

type AgentStripProps = {
  agents: { state: AgentState; project: ProjectObject }[];
};

export function AgentStrip({ agents }: AgentStripProps) {
  if (agents.length === 0) {
    return (
      <p className="text-xs text-[var(--muted)]">
        本阶段暂无智能体运行摘要（原型，后续可接实时编排）。
      </p>
    );
  }
  return (
    <ul className="space-y-2">
      {agents.map(({ state, project }) => (
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
              href={`/projects/${project.id}`}
              className="text-[var(--accent)] hover:underline"
            >
              {project.name}
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
