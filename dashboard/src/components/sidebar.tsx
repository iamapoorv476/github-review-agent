"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  {
    href: "/dashboard",
    label: "Reviews",
    count: "128",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-[15px] w-[15px] flex-none">
        <path d="M2 3h12M2 8h12M2 13h8" />
      </svg>
    ),
  },
  {
    href: "/dashboard/settings",
    label: "Repos & rules",
    count: "3",
    icon: (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" className="h-[15px] w-[15px] flex-none">
        <circle cx="8" cy="8" r="2.6" />
        <path d="M8 1.5v2M8 12.5v2M1.5 8h2M12.5 8h2M3.4 3.4l1.4 1.4M11.2 11.2l1.4 1.4M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4" />
      </svg>
    ),
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="ruled sticky top-0 flex h-screen flex-col gap-1 border-r border-line px-3.5 py-5 max-md:static max-md:h-auto max-md:flex-row max-md:items-center max-md:border-b max-md:border-r-0">
      <Link href="/" className="flex items-baseline gap-2 px-2 pb-4 no-underline max-md:pb-0">
        <span className="voice text-[27px] leading-none font-medium text-rubric">¶</span>
        <span className="text-[16.5px] font-semibold tracking-tight text-ink">
          Marginalia
          <em className="voice block text-[11px] font-medium text-ink-3">notes in your margins</em>
        </span>
      </Link>

      <div className="px-2 pb-1.5 pt-3 text-[10.5px] font-semibold uppercase tracking-[0.14em] text-ink-3 max-md:hidden">
        Workspace
      </div>

      {NAV.map((item) => {
        const active =
          item.href === "/dashboard"
            ? pathname === "/dashboard" || pathname.startsWith("/dashboard/reviews")
            : pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-[13.5px] font-medium no-underline transition-colors ${
              active ? "bg-ink text-raised" : "text-ink-2 hover:bg-recess hover:text-ink"
            }`}
          >
            {item.icon}
            {item.label}
            <span className={`ml-auto font-mono text-[11px] ${active ? "text-white/55" : "text-ink-3"}`}>
              {item.count}
            </span>
          </Link>
        );
      })}

      <div className="mt-4 rounded-lg border border-line bg-raised p-3 max-md:hidden" role="status">
        <div className="flex items-center gap-2 text-xs font-semibold">
          <span className="pulse-dot h-[7px] w-[7px] flex-none rounded-full bg-verdigris" />
          1 review running
        </div>
        <div className="mt-1 text-[11.5px] leading-normal text-ink-2">
          <code className="rounded bg-recess px-1 font-mono text-[10.5px]">acme/web-app</code> #517 —
          reading diff, step 4 of ~9
        </div>
      </div>

      <div className="mt-auto border-t border-line px-2 pt-2.5 text-[11.5px] leading-relaxed text-ink-3 max-md:hidden">
        Installed on <b className="font-semibold text-ink-2">acme</b> · 3 repos
        <br />
        App v0.5 · queue healthy
      </div>
    </aside>
  );
}
