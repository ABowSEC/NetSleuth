import { describe, expect, it } from "vitest";
import { toDevice, toDeviceDetail, toDevices, toEvent, toIdentify, toSettings } from "./guards";

describe("toDevice", () => {
  it("keeps well-formed fields", () => {
    const d = toDevice({
      mac: "aa:bb:cc:dd:ee:01", name: "Laptop", hostname: "lap", vendor: "Acme", type: "computer",
      is_known: true, online: true, ips: ["192.168.1.2"], first_seen: "2026-01-01T00:00:00Z",
      last_seen: "2026-01-02T00:00:00Z", notes: null,
    });
    expect(d).toMatchObject({ name: "Laptop", type: "computer", is_known: true, ips: ["192.168.1.2"] });
  });

  it("degrades malformed fields instead of throwing", () => {
    // The old dashboard crashed on a non-string hostname.
    const d = toDevice({ mac: "aa:bb:cc:dd:ee:02", hostname: { name: "x" }, type: "spaceship", ips: [1, "10.0.0.1"], online: "yes" });
    expect(d.hostname).toBeNull();
    expect(d.type).toBe("unknown");
    expect(d.ips).toEqual(["10.0.0.1"]);
    expect(d.online).toBe(false);
    expect(d.first_seen).toBe("");
  });

  it("treats blank strings as missing", () => {
    expect(toDevice({ mac: "m", name: "   " }).name).toBeNull();
  });
});

it("toDevices drops entries without a MAC and tolerates non-arrays", () => {
  expect(toDevices([{ mac: "a" }, { name: "no mac" }, null])).toHaveLength(1);
  expect(toDevices({ not: "a list" })).toEqual([]);
});

it("toEvent falls back to safe kind and severity", () => {
  const e = toEvent({ id: 3, kind: "weird", severity: "apocalyptic", message: "m", data: "nope" });
  expect(e).toMatchObject({ id: 3, kind: "alert", severity: "info", data: {} });
});

it("toSettings fills defaults", () => {
  expect(toSettings({ sweep_interval_s: 60 })).toEqual({
    offline_timeout_s: 600, sweep_interval_s: 60, retention_days: 30, lan_exposure: false, anomaly_plugin: false,
    port_check: false, identify_minutes: 10,
  });
});

it("device identification fields default to null", () => {
  const d = toDevice({ mac: "m" });
  expect([d.model, d.os, d.suggested_name]).toEqual([null, null, null]);
});

it("detail evidence and suggestion are shaped defensively", () => {
  const detail = toDeviceDetail({
    mac: "m",
    evidence: [{ source: "upnp", key: "modelName", value: "Roku Ultra", confidence: 1 }, { source: "x", key: "", value: "" }, 5],
    suggestion: { name: "Bedroom Roku", model: 7, type: "tv" },
  });
  expect(detail.evidence).toEqual([
    { source: "upnp", key: "modelName", value: "Roku Ultra", confidence: 1, last_seen: "" },
  ]);
  expect(detail.suggestion).toEqual({ name: "Bedroom Roku", model: null, os: null, type: "tv" });
  expect(toDeviceDetail({ mac: "m", suggestion: null }).suggestion).toBeNull();
});

it("identify status defaults to idle", () => {
  expect(toIdentify(null)).toEqual({
    running: false, started_at: null, ends_at: null, done: 0, total: 0, current: null, port_check: false,
  });
  expect(toIdentify({ running: true, done: 3, total: 9 })).toMatchObject({ running: true, done: 3, total: 9 });
});
