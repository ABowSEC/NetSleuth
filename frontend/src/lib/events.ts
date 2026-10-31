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

export const ACTIVITY_FILTERS = [
  { id: "all", label: "Everything", test: () => true },
  { id: "attention", label: "Needs attention", test: isImportant },
  { id: "presence", label: "Comings and goings", test: (e: NetEvent) => e.kind === "joined" || e.kind === "left" },
  { id: "security", label: "Security", test: (e: NetEvent) => e.kind === "mac_conflict" || e.kind === "alert" },
] as const;
export type ActivityFilter = (typeof ACTIVITY_FILTERS)[number]["id"];

/** Short verb shown in the log's second column. */
export const KIND_VERBS: Record<NetEvent["kind"], string> = {
  new_device: "new",
  joined: "arrived",
  left: "left",
  ip_changed: "new IP",
  mac_conflict: "clash",
  alert: "alert",
};
