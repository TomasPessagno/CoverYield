"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Screener" },
  { href: "/scan", label: "Scan" },
];

function toggleTheme() {
  const root = document.documentElement;
  const current =
    root.dataset.theme ?? (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const next = current === "dark" ? "light" : "dark";
  root.dataset.theme = next;
  try {
    localStorage.setItem("theme", next);
  } catch {
    // storage unavailable (private mode): the choice lasts for this page view
  }
}

export function TopBar() {
  const pathname = usePathname();
  return (
    <header className="sticky top-0 z-20 border-b border-border bg-bg/90 backdrop-blur">
      <div className="mx-auto flex h-12 w-full max-w-[1440px] items-center gap-8 px-4 sm:px-6">
        <Link href="/" className="text-[15px] font-semibold tracking-tight">
          ThetaScout
        </Link>
        <nav className="flex h-full items-stretch gap-6">
          {NAV.map(({ href, label }) => {
            const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`flex items-center border-b-2 text-sm transition-colors ${
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
        <span className="label ml-auto hidden sm:block">Yahoo Finance · delayed</span>
        <button
          type="button"
          onClick={toggleTheme}
          aria-label="Toggle light and dark mode"
          title="Toggle light and dark mode"
          className="ml-auto flex h-8 w-8 items-center justify-center rounded-sm text-text-2 hover:bg-panel-2 hover:text-text sm:ml-0"
        >
          <svg className="theme-icon-moon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
          </svg>
          <svg className="theme-icon-sun" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </svg>
        </button>
      </div>
    </header>
  );
}
