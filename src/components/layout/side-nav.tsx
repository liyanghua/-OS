"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { getMainNavSections } from "@/config/nav";

function navLinkClass(active: boolean): string {
  return `block rounded-[var(--radius-md)] px-2.5 py-2 text-sm font-medium tracking-tight transition-[color,background-color,box-shadow] duration-150 ${
    active
      ? "bg-[var(--accent-muted)] text-[var(--accent)] shadow-[inset_3px_0_0_0_var(--accent)]"
      : "text-[var(--muted)] hover:bg-[var(--surface-elevated)]/80 hover:text-[var(--foreground)]"
  }`;
}

export function SideNav() {
  const pathname = usePathname();
  const sections = getMainNavSections();

  return (
    <nav className="flex h-full w-[15.5rem] min-w-[15.5rem] flex-col gap-6 border-r border-[var(--border)] bg-[var(--surface)] bg-gradient-to-b from-[var(--surface)] to-[var(--strip-bg)] px-3 py-5 shadow-[inset_-1px_0_0_rgba(255,255,255,0.03)]">
      <div className="px-1">
        <Link
          href="/command-center"
          className="text-sm font-semibold tracking-tight text-[var(--foreground)] transition-colors hover:text-[var(--accent-hover)]"
        >
          经营操盘系统
        </Link>
        <p className="mt-1 text-[11px] leading-relaxed text-[var(--muted)]">
          以商品经营为主线 · 围绕商品项目 · 优先看经营脉冲与异常
        </p>
      </div>
      {sections.map((section) => (
        <div key={section.id}>
          {section.label ? (
            <p className="mb-2 px-1 text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-2)]">
              {section.label}
            </p>
          ) : null}
          <ul className="flex flex-col gap-0.5">
            {section.items.map((item) => {
              const active =
                item.href === "/lifecycle"
                  ? pathname === "/lifecycle"
                  : pathname === item.href ||
                    pathname.startsWith(`${item.href}/`);
              return (
                <li key={item.href}>
                  <Link href={item.href} className={navLinkClass(active)}>
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </nav>
  );
}
