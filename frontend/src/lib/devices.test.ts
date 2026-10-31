import { expect, it } from "vitest";
import { groupDevices } from "./devices";
import type { Device } from "./types";

const device = (mac: string, partial: Partial<Device>): Device => ({
  mac, name: null, hostname: null, vendor: null, type: "unknown", is_known: false, online: false,
  ips: [], first_seen: "2026-10-01T00:00:00Z", last_seen: "2026-10-30T00:00:00Z", notes: null, ...partial,
});

const devices = [
  device("01", { name: "Zed laptop", online: true, is_known: true, ips: ["192.168.1.9"] }),
  device("02", { name: "Alpha phone", online: true, is_known: true }),
  device("03", { vendor: "Roku, Inc", online: true, first_seen: "2026-10-29T00:00:00Z" }),
  device("04", { vendor: "Acme", online: true, first_seen: "2026-10-30T00:00:00Z" }),
  device("05", { vendor: "Old thing", online: false, first_seen: "2026-10-30T06:00:00Z" }),
  device("06", { name: "Printer", is_known: true, last_seen: "2026-10-29T00:00:00Z" }),
  device("07", { name: "Xbox", is_known: true, last_seen: "2026-10-30T09:00:00Z" }),
];

const macs = (list: Device[]) => list.map((d) => d.mac);

it("splits devices into unrecognised, here and away", () => {
  const groups = groupDevices(devices);
  expect(macs(groups.unrecognised)).toEqual(["04", "03", "05"]); // online first, newest arrival first
  expect(macs(groups.here)).toEqual(["02", "01"]);               // by name
  expect(macs(groups.away)).toEqual(["07", "06"]);               // most recently seen first
});

it("searches names, vendors and IPs across every group", () => {
  expect(macs(groupDevices(devices, "roku").unrecognised)).toEqual(["03"]);
  const byIp = groupDevices(devices, "192.168.1.9");
  expect([...macs(byIp.unrecognised), ...macs(byIp.here), ...macs(byIp.away)]).toEqual(["01"]);
});
