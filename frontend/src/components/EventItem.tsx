import Link from "next/link";
import { SeverityTag } from "./ui";
import { timeOfDay } from "@/lib/format";
import type { EventKind, NetEvent } from "@/lib/types";

export const KIND_LABELS: Record<EventKind, string> = {
  new_device: "New devices",
  joined: "Joined",
  left: "Left",
  ip_changed: "IP changes",
  mac_conflict: "Address conflicts",
  alert: "Security alerts",
};

const KIND_STYLE: Record<EventKind, { tone: string; path: React.ReactNode }> = {
  new_device: { tone: "bg-warn/15 text-warn", path: <path d="M12 5v14M5 12h14" /> },
  joined: { tone: "bg-ok/15 text-ok", path: <path d="M5 12h12M12 6l6 6-6 6" /> },
  left: { tone: "bg-surface-2 text-muted", path: <path d="M19 12H7M12 6l-6 6 6 6" /> },
  ip_changed: { tone: "bg-info/15 text-info", path: <path d="M4 8h13l-3-3M20 16H7l3 3" /> },
  mac_conflict: { tone: "bg-danger/15 text-danger", path: <path d="M12 4 2.5 20h19L12 4Zm0 6v4m0 3h.01" /> },
  alert: { tone: "bg-danger/15 text-danger", path: <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6l-8-3Zm0 6v4m0 3h.01" /> },
};

export function EventItem({ event }: { event: NetEvent }) {
  const style = KIND_STYLE[event.kind];
  return (
    <li className="flex gap-3 px-4 py-3">
      <span className={`mt-0.5 grid size-8 shrink-0 place-items-center rounded-full ${style.tone}`}>
        <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          {style.path}
        </svg>
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm">
          {event.message}
          {" "}
          <SeverityTag severity={event.severity} />
        </p>
        <p className="mt-0.5 flex flex-wrap gap-x-3 text-xs text-muted">
          <time dateTime={event.ts}>{timeOfDay(event.ts)}</time>
          {event.mac && (
            <Link href={`/?device=${encodeURIComponent(event.mac)}`} className="hover:text-accent hover:underline">
              View device
            </Link>
          )}
        </p>
      </div>
    </li>
  );
}
