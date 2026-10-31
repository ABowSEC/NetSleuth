import { displayName, matchesQuery } from "./format";
import type { Device } from "./types";

export interface DeviceGroups {
  /** Not marked as known yet: newest arrivals first, online before offline. */
  unrecognised: Device[];
  /** Known and on the network now, by name. */
  here: Device[];
  /** Known and gone, most recently seen first. */
  away: Device[];
}

const byName = (a: Device, b: Device) => displayName(a).localeCompare(displayName(b));
const newest = (key: "first_seen" | "last_seen") => (a: Device, b: Device) => b[key].localeCompare(a[key]);

export function groupDevices(devices: Device[], query = ""): DeviceGroups {
  const matching = devices.filter((d) => matchesQuery(d, query));
  return {
    unrecognised: matching
      .filter((d) => !d.is_known)
      .sort((a, b) => Number(b.online) - Number(a.online) || newest("first_seen")(a, b)),
    here: matching.filter((d) => d.is_known && d.online).sort(byName),
    away: matching.filter((d) => d.is_known && !d.online).sort(newest("last_seen")),
  };
}
