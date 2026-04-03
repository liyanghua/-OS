import type { ReactNode } from "react";
import { AiGlyph } from "@/components/ui/ai-glyph";

type AiSignalFrameProps = {
  /** 顶栏标签，如「经营大脑 · 摘要」 */
  label: string;
  children: ReactNode;
  /** 角标：如置信度、更新时间 */
  footer?: ReactNode;
  className?: string;
};

/** AI 生成内容容器：冷色渐变壳 + 星形 glyph（原则文档 2.2） */
export function AiSignalFrame({
  label,
  children,
  footer,
  className = "",
}: AiSignalFrameProps) {
  return (
    <div
      className={`rounded-lg border border-sky-500/20 bg-gradient-to-br from-sky-500/[0.1] via-violet-500/[0.06] to-transparent px-3 py-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.05)] ${className}`}
    >
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-sky-100/95 md:text-sm">
        <AiGlyph className="h-4 w-4 shrink-0 text-sky-300/95 md:h-[1.125rem] md:w-[1.125rem]" />
        <span>{label}</span>
      </div>
      <div className="mt-2.5 text-base leading-relaxed text-[var(--foreground)]">
        {children}
      </div>
      {footer ? (
        <div className="mt-2 border-t border-white/[0.06] pt-2 text-xs text-[var(--muted)]">
          {footer}
        </div>
      ) : null}
    </div>
  );
}
