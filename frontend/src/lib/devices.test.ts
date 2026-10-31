import { expect, it } from "vitest";
import { filterDevices, isFilter } from "./devices";
import type { Device } from "./types";

const device = (mac: string, partial: Partial<Device>): Device => ({
  mac, name: null, hostname: null, vendor: null, type: "unknown", is_known: false, online: false,
  ips: [], first_seen: "", last_seen: "", notes: null, ...partial,
});

const devices = [
  device("01", { name: "Zed laptop", online: true, is_known: true, ips: ["192.168.1.9"] }),
  device("02", { name: "Alpha phone", online: true, is_known: true }),
  device("03", { vendor: "Roku, Inc", online: true }),
  device("04", { name: "Printer", is_known: true }),
];

it("sorts online first, then unreviewed, then by name", () => {
  expect(filterDevices(devices, "all", "").map((d) => d.mac)).toEqual(["03", "02", "01", "04"]);
});

it("filters by status and review state", () => {
  expect(filterDevices(devices, "online", "").map((d) => d.mac)).toEqual(["03", "02", "01"]);
  expect(filterDevices(devices, "offline", "").map((d) => d.mac)).toEqual(["04"]);
  expect(filterDevices(devices, "review", "").map((d) => d.mac)).toEqual(["03"]);
});

it("searches names, vendors and IPs", () => {
  expect(filterDevices(devices, "all", "roku").map((d) => d.mac)).toEqual(["03"]);
  expect(filterDevices(devices, "all", "192.168.1.9").map((d) => d.mac)).toEqual(["01"]);
});

it("validates filter params from the URL", () => {
  expect(isFilter("review")).toBe(true);
  expect(isFilter("bogus")).toBe(false);
  expect(isFilter(null)).toBe(false);
});
