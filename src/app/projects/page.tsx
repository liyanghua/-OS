import Link from "next/link";
import { PagePlaceholder } from "@/components/shell/page-placeholder";
import { createMockProjects } from "@/state/mock-projects";

export default function ProjectsIndexPage() {
  const projects = createMockProjects();

  return (
    <div className="space-y-8">
      <PagePlaceholder
        title="商品项目"
        route="/projects"
        intent={[
          "商品项目列表：每一行对应一个可经营的商品项目（后续里程碑完善列表与筛选）。",
          "以下为当前 mock 存储中的全部商品项目，用于联调详情骨架。",
        ]}
      />
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-4">
        <p className="mb-3 text-xs font-medium tracking-wide text-[var(--muted)]">
          示例商品项目
        </p>
        <ul className="flex flex-col gap-2 text-sm">
          {projects.map((p) => (
            <li key={p.id}>
              <Link
                href={`/projects/${p.id}`}
                className="text-[var(--accent)] hover:underline"
              >
                {p.name}（{p.id}）
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
