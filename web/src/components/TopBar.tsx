"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Screener" },
  { href: "/scan", label: "Scan" },
];

export function TopBar() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/95 backdrop-blur">
      <div className="mx-auto flex h-11 w-full max-w-[1440px] items-center gap-8 px-4 sm:px-6">
        <Link href="/" className="font-mono text-sm font-semibold tracking-[0.18em]">
          THETA<span className="text-accent">SCOUT</span>
        </Link>
        <nav className="flex h-full items-stretch gap-6">
          {NAV.map(({ href, label }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center border-b-2 font-mono text-xs uppercase tracking-[0.12em] transition-colors ${
                  active
                    ? "border-accent text-text"
                    : "border-transparent text-muted hover:text-text-2"
                }`}
              >
                {label}
              </Link>
            );
          })}
        </nav>
        <span className="label ml-auto hidden sm:block">Yahoo Finance · Delayed</span>
      </div>
    </header>
  );
}
