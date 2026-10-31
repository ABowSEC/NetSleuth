"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLive, type LiveStatus } from "@/context/LiveContext";
import { useTheme, type ThemeMode } from "@/context/ThemeContext";

const NAV = [
  { href: "/", label: "Devices" },
  { href: "/activity", label: "Activity" },
  { href: "/settings", label: "Settings" },
];

const STATUS: Record<LiveStatus, { label: string; dot: string }> = {
  live: { label: "Live", dot: "bg-ok" },
  polling: { label: "Updating", dot: "bg-ok" },
  connecting: { label: "Connecting", dot: "bg-warn animate-pulse" },
  offline: { label: "Offline", dot: "bg-danger" },
};

const NEXT_THEME: Record<ThemeMode, ThemeMode> = { system: "light", light: "dark", dark: "system" };

function ThemeButton() {
  const { mode, setMode } = useTheme();
  return (
    <button
      type="button"
      onClick={() => setMode(NEXT_THEME[mode])}
      className="grid size-9 place-items-center rounded-md text-muted hover:bg-surface-2 hover:text-text"
      title={`Theme: ${mode} (click to change)`}
      aria-label={`Theme: ${mode}. Switch to ${NEXT_THEME[mode]}`}
    >
      <svg viewBox="0 0 24 24" className="size-[18px]" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" aria-hidden="true">
        {mode === "dark" ? (
          <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
        ) : mode === "light" ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
          </>
        ) : (
          <>
            <rect x="3" y="4" width="18" height="12" rx="1.5" />
            <path d="M8 20h8M12 16v4" />
          </>
        )}
      </svg>
    </button>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const { status, health } = useLive();
  const paused = health !== null && !health.capturing && status !== "offline";
  const badge = paused ? { label: "Paused", dot: "bg-warn" } : STATUS[status];

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-bg/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-2 px-4 sm:gap-6">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <svg viewBox="0 0 24 24" className="size-6 text-accent" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" />
            <path d="m20.5 20.5-4.9-4.9M8 11h.01M11 11h.01M14 11h.01" />
          </svg>
          <span className="hidden sm:inline">NetSleuth</span>
        </Link>

        <nav className="flex items-center gap-1" aria-label="Main">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`rounded-md px-2.5 py-1.5 text-sm font-medium transition-colors sm:px-3 ${
                  active ? "bg-surface-2 text-text" : "text-muted hover:text-text"
                }`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-1 sm:gap-3">
          <span
            className="flex items-center gap-2 text-xs font-medium text-muted"
            title={health?.interface ? `Watching ${health.interface}` : undefined}
          >
            <span className={`size-2 rounded-full ${badge.dot}`} aria-hidden="true" />
            <span className="hidden sm:inline">{badge.label}</span>
            <span className="sr-only sm:hidden">{badge.label}</span>
          </span>
          <ThemeButton />
        </div>
      </div>
    </header>
  );
}
