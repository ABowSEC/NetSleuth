import { displayName, matchesQuery } from "./format";
import type { Device } from "./types";

export const FILTERS = [
  { id: "all", label: "All" },
  { id: "online", label: "Online" },
  { id: "review", label: "Needs review" },
  { id: "offline", label: "Offline" },
] as const;
export type Filter = (typeof FILTERS)[number]["id"];

export const isFilter = (v: string | null): v is Filter => FILTERS.some((f) => f.id === v);

export function filterDevices(devices: Device[], filter: Filter, query: string): Device[] {
  return devices
    .filter((d) =>
      (filter === "online" ? d.online : filter === "offline" ? !d.online : filter === "review" ? !d.is_known : true)
      && matchesQuery(d, query))
    .sort((a, b) =>
      Number(b.online) - Number(a.online)
      || Number(a.is_known) - Number(b.is_known)
      || displayName(a).localeCompare(displayName(b)));
}
