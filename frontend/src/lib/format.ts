import type { Device, DeviceType } from "./types";

/** Best human label for a device: user name, then hostname, then vendor. */
export function displayName(d: Pick<Device, "name" | "hostname" | "vendor">): string {
  return d.name ?? d.hostname ?? (d.vendor ? `${shortVendor(d.vendor)} device` : "Unknown device");
}

/** "Amazon Technologies Inc." -> "Amazon Technologies" */
export function shortVendor(vendor: string): string {
  return vendor
    .replace(/[,.]?\s+(inc|llc|ltd|co|corp|corporation|corporate|gmbh|limited|technology|tech)\.?(?=\s|,|$)/gi, "")
    .replace(/[,.\s]+$/, "")
    .trim() || vendor;
}

export const TYPE_LABELS: Record<DeviceType, string> = {
  router: "Router",
  computer: "Computer",
  phone: "Phone",
  tablet: "Tablet",
  tv: "TV / streaming",
  speaker: "Speaker",
  camera: "Camera",
  printer: "Printer",
  console: "Game console",
  iot: "Smart home",
  unknown: "Unknown type",
};

const toDate = (iso: string): Date | null => {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
};

/**
 * Reads inside a sentence: "left 3 hours ago", "first seen just now",
 * "left on 9/30/2026", "left at an unknown time".
 */
export function relativeTime(iso: string, now: number = Date.now()): string {
  const d = toDate(iso);
  if (!d) return "at an unknown time";
  const s = Math.max(0, Math.round((now - d.getTime()) / 1000));
  const ago = (n: number, unit: string) => `${n} ${unit}${n === 1 ? "" : "s"} ago`;
  if (s < 45) return "just now";
  if (s < 3600) return ago(Math.max(1, Math.round(s / 60)), "minute");
  if (s < 86400) return ago(Math.round(s / 3600), "hour");
  if (s < 86400 * 30) return ago(Math.round(s / 86400), "day");
  return `on ${d.toLocaleDateString()}`;
}

export function dateTime(iso: string): string {
  const d = toDate(iso);
  return d ? d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }) : "—";
}

export function timeOfDay(iso: string): string {
  const d = toDate(iso);
  return d ? d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "—";
}

/** Group label for an event list: "Today", "Yesterday", or a date. */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const d = toDate(iso);
  if (!d) return "Unknown date";
  const startOf = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((startOf(now) - startOf(d)) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
}

export function duration(seconds: number): string {
  if (seconds % 86400 === 0) return `${seconds / 86400} day${seconds === 86400 ? "" : "s"}`;
  if (seconds % 3600 === 0) return `${seconds / 3600} hour${seconds === 3600 ? "" : "s"}`;
  if (seconds % 60 === 0) return `${seconds / 60} min`;
  return `${seconds} s`;
}

export function matchesQuery(d: Device, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (!needle) return true;
  return [d.name, d.hostname, d.vendor, d.mac, ...d.ips].some((v) => v?.toLowerCase().includes(needle));
}
