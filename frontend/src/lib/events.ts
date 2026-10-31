import { dayLabel } from "./format";
import type { NetEvent } from "./types";

/** Group consecutive events (newest first) by local calendar day. */
export function groupByDay(events: NetEvent[], now = new Date()): { label: string; events: NetEvent[] }[] {
  const groups: { label: string; events: NetEvent[] }[] = [];
  for (const event of events) {
    const label = dayLabel(event.ts, now);
    const last = groups[groups.length - 1];
    if (last && last.label === label) last.events.push(event);
    else groups.push({ label, events: [event] });
  }
  return groups;
}

export const isImportant = (e: NetEvent) =>
  e.kind === "new_device" || e.kind === "mac_conflict" || e.kind === "alert" || e.severity !== "info";
