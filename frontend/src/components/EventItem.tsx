import Link from "next/link";
import { KIND_VERBS } from "@/lib/events";
import { timeOfDay } from "@/lib/format";
import type { NetEvent } from "@/lib/types";

// Colour follows meaning: green arrivals, amber strangers, red trouble, muted routine.
function verbTone(e: NetEvent): string {
  if (e.kind === "mac_conflict" || e.kind === "alert" || e.severity === "high" || e.severity === "critical") return "text-danger";
  if (e.kind === "new_device" && e.data.baseline !== true) return "text-warn";
  if (e.kind === "joined") return "text-ok";
  return "text-muted";
}

/** One line of the activity log: time, verb, what happened. */
export function EventItem({ event }: { event: NetEvent }) {
  const serious = event.severity === "critical";
  return (
    <li className={`grid grid-cols-[4.5rem_4.5rem_1fr] gap-x-3 px-4 py-2.5 text-sm ${serious ? "bg-danger/5" : ""}`}>
      <time dateTime={event.ts} className="font-mono text-xs leading-5 text-muted tabular-nums">
        {timeOfDay(event.ts)}
      </time>
      <span className={`text-xs font-semibold uppercase leading-5 tracking-wide ${verbTone(event)}`}>
        {KIND_VERBS[event.kind]}
      </span>
      <p className="min-w-0">
        {event.message}
        {event.mac && (
          <>
            {" "}
            <Link
              href={`/?device=${encodeURIComponent(event.mac)}`}
              className="whitespace-nowrap text-muted underline decoration-border underline-offset-2 hover:text-text"
            >
              open device
            </Link>
          </>
        )}
      </p>
    </li>
  );
}
