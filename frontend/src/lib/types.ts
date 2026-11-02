// Mirrors docs/API_CONTRACT.md (v1).

export const DEVICE_TYPES = [
  "router", "computer", "phone", "tablet", "tv", "speaker",
  "camera", "printer", "console", "iot", "unknown",
] as const;
export type DeviceType = (typeof DEVICE_TYPES)[number];

export interface Device {
  mac: string;
  name: string | null;
  hostname: string | null;
  vendor: string | null;
  type: DeviceType;
  is_known: boolean;
  online: boolean;
  ips: string[];
  first_seen: string;
  last_seen: string;
  notes: string | null;
  // Identification, derived from evidence (null when unknown)
  model: string | null;
  os: string | null;
  suggested_name: string | null;
}

export interface DomainCount {
  domain: string;
  count: number;
  last_seen: string;
}

export interface DestinationCount {
  address: string;
  port: number | null;
  count: number;
  last_seen: string;
}

export interface PresenceSession {
  start: string;
  end: string | null;
}

export const EVIDENCE_SOURCES = ["upnp", "roku", "mdns", "netbios", "rdns", "dhcp", "ssdp", "ports"] as const;
export type EvidenceSource = (typeof EVIDENCE_SOURCES)[number];

export interface EvidenceItem {
  source: EvidenceSource;
  key: string;
  value: string;
  confidence: number;
  last_seen: string;
}

export interface Suggestion {
  name: string | null;
  model: string | null;
  os: string | null;
  type: DeviceType;
}

export interface DeviceDetail extends Device {
  top_domains: DomainCount[];
  top_destinations: DestinationCount[];
  presence: PresenceSession[];
  evidence: EvidenceItem[];
  suggestion: Suggestion | null;
}

export const EVENT_KINDS = [
  "joined", "left", "new_device", "ip_changed", "mac_conflict", "alert", "identified",
] as const;
export type EventKind = (typeof EVENT_KINDS)[number];

export const SEVERITIES = ["info", "low", "medium", "high", "critical"] as const;
export type Severity = (typeof SEVERITIES)[number];

export interface NetEvent {
  id: number;
  ts: string;
  kind: EventKind;
  mac: string | null;
  severity: Severity;
  message: string;
  data: Record<string, unknown>;
}

export interface Summary {
  online: number;
  offline: number;
  unknown: number;
  total: number;
  last_update: string;
}

export interface Health {
  status: "ok";
  version: string;
  capturing: boolean;
  interface: string | null;
}

export interface Settings {
  offline_timeout_s: number;
  sweep_interval_s: number;
  retention_days: number;
  lan_exposure: boolean;
  anomaly_plugin: boolean;
  port_check: boolean;
  identify_minutes: number;
}

/** Identify mode: active probing that switches itself off. */
export interface IdentifyStatus {
  running: boolean;
  started_at: string | null;
  ends_at: string | null;
  done: number;
  total: number;
  current: string | null;
  port_check: boolean;
}

export interface DevicePatch {
  name?: string | null;
  is_known?: boolean;
  notes?: string | null;
}
