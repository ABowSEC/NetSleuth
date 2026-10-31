// Runtime shaping of API responses. A malformed field degrades to a safe
// default instead of crashing the page (the old UI died on a non-string hostname).

import {
  DEVICE_TYPES, EVENT_KINDS, SEVERITIES,
  type Device, type DeviceDetail, type DeviceType, type EventKind, type Health,
  type NetEvent, type Settings, type Severity, type Summary,
} from "./types";

type Obj = Record<string, unknown>;

const obj = (v: unknown): Obj => (v && typeof v === "object" && !Array.isArray(v) ? (v as Obj) : {});
const str = (v: unknown, fallback = ""): string => (typeof v === "string" ? v : fallback);
const optStr = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const num = (v: unknown, fallback = 0): number => (typeof v === "number" && Number.isFinite(v) ? v : fallback);
const bool = (v: unknown): boolean => v === true;
const arr = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const oneOf = <T extends string>(v: unknown, allowed: readonly T[], fallback: T): T =>
  allowed.includes(v as T) ? (v as T) : fallback;

export function toDevice(raw: unknown): Device {
  const d = obj(raw);
  return {
    mac: str(d.mac),
    name: optStr(d.name),
    hostname: optStr(d.hostname),
    vendor: optStr(d.vendor),
    type: oneOf<DeviceType>(d.type, DEVICE_TYPES, "unknown"),
    is_known: bool(d.is_known),
    online: bool(d.online),
    ips: arr(d.ips).filter((ip): ip is string => typeof ip === "string"),
    first_seen: str(d.first_seen),
    last_seen: str(d.last_seen),
    notes: optStr(d.notes),
  };
}

export function toDevices(raw: unknown): Device[] {
  return arr(raw).map(toDevice).filter((d) => d.mac);
}

export function toDeviceDetail(raw: unknown): DeviceDetail {
  const d = obj(raw);
  return {
    ...toDevice(d),
    top_domains: arr(d.top_domains).map((x) => {
      const o = obj(x);
      return { domain: str(o.domain), count: num(o.count), last_seen: str(o.last_seen) };
    }),
    top_destinations: arr(d.top_destinations).map((x) => {
      const o = obj(x);
      return {
        address: str(o.address),
        port: typeof o.port === "number" ? o.port : null,
        count: num(o.count),
        last_seen: str(o.last_seen),
      };
    }),
    presence: arr(d.presence).map((x) => {
      const o = obj(x);
      return { start: str(o.start), end: optStr(o.end) };
    }),
  };
}

export function toEvent(raw: unknown): NetEvent {
  const e = obj(raw);
  return {
    id: num(e.id),
    ts: str(e.ts),
    kind: oneOf<EventKind>(e.kind, EVENT_KINDS, "alert"),
    mac: optStr(e.mac),
    severity: oneOf<Severity>(e.severity, SEVERITIES, "info"),
    message: str(e.message),
    data: obj(e.data),
  };
}

export function toEvents(raw: unknown): NetEvent[] {
  return arr(raw).map(toEvent);
}

export function toSummary(raw: unknown): Summary {
  const s = obj(raw);
  return {
    online: num(s.online),
    offline: num(s.offline),
    unknown: num(s.unknown),
    total: num(s.total),
    last_update: str(s.last_update),
  };
}

export function toHealth(raw: unknown): Health {
  const h = obj(raw);
  return {
    status: "ok",
    version: str(h.version),
    capturing: bool(h.capturing),
    interface: optStr(h.interface),
  };
}

export function toSettings(raw: unknown): Settings {
  const s = obj(raw);
  return {
    offline_timeout_s: num(s.offline_timeout_s, 600),
    sweep_interval_s: num(s.sweep_interval_s, 300),
    retention_days: num(s.retention_days, 30),
    lan_exposure: bool(s.lan_exposure),
    anomaly_plugin: bool(s.anomaly_plugin),
  };
}
