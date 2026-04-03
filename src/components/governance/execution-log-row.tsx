import type { ExecutionLog } from "@/domain/types";
import { executionStatusLabel } from "@/domain/mappers/display-zh";

const ACTOR_PHRASE: Record<ExecutionLog["actorType"], string> = {
  human: "人为发起方",
  agent: "智能体",
  automation: "自动化",
};

type ExecutionLogRowProps = {
  log: ExecutionLog;
};

export function ExecutionLogRow({ log }: ExecutionLogRowProps) {
  const who = ACTOR_PHRASE[log.actorType];
  const status = executionStatusLabel(log.status);
  const when = new Date(log.updatedAt).toLocaleString("zh-CN");
  return (
    <div className="rounded-[var(--radius-md)] border border-[var(--border)]/85 bg-[var(--surface-elevated)]/35 px-3 py-2.5 text-xs shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <p className="text-[var(--foreground)] leading-relaxed">
        <span className="font-medium">{who}</span>
        <span className="text-[var(--muted)]">（{log.actorId}）</span>
        于 <span className="text-[var(--muted)]">{when}</span> 将关联动作{" "}
        <code className="rounded bg-[var(--border)]/25 px-1 text-[11px]">
          {log.actionId}
        </code>{" "}
        的执行状态更新为<span className="font-medium">「{status}」</span>：
        <span className="text-[var(--muted)]">{log.summary}</span>
      </p>
    </div>
  );
}
