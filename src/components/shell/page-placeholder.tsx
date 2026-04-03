type PagePlaceholderProps = {
  title: string;
  route: string;
  intent: string[];
};

/**
 * M1 skeleton — signals lifecycle-driven, project-object-centered,
 * pulse / exception / agent / review-to-asset intent (ARCHITECTURE §8).
 */
export function PagePlaceholder({ title, route, intent }: PagePlaceholderProps) {
  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <p className="text-xs font-medium tracking-wide text-[var(--muted)]">
          页面占位（骨架）
        </p>
        <h1 className="app-page-title mt-1">{title}</h1>
        <code className="mt-1 block text-sm text-[var(--accent)]">{route}</code>
      </div>
      <ul className="list-inside list-disc space-y-2 text-sm text-[var(--muted)]">
        {intent.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}
