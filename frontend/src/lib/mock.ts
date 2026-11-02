// In-memory stand-in for the backend, enabled with NEXT_PUBLIC_MOCK=1.
// Lets the UI run (and be tested) without the capture service.
// All data is invented: locally administered MACs and a documentation-style LAN.

import type { Api } from "./api";
import { ApiError } from "./errors";
import type {
  Device, DeviceDetail, EvidenceItem, IdentifyStatus, NetEvent, Settings, Summary,
} from "./types";

const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString().replace(/\.\d{3}Z$/, "Z");

function seedDevices(): Device[] {
  const d = (
    mac: string, ip: string, partial: Partial<Device>, lastSeenMin = 0, firstSeenMin = 60 * 24 * 12,
  ): Device => ({
    mac, name: null, hostname: null, vendor: null, type: "unknown", is_known: false,
    online: lastSeenMin < 10, ips: [ip], first_seen: minutesAgo(firstSeenMin),
    last_seen: minutesAgo(lastSeenMin), notes: null, model: null, os: null, suggested_name: null, ...partial,
  });
  return [
    d("02:00:00:00:00:01", "192.168.1.1", { vendor: "Example Networks", type: "router", name: "Router", is_known: true }),
    d("02:00:00:00:00:10", "192.168.1.20", { hostname: "family-laptop", type: "computer", name: "Family laptop", is_known: true }, 1),
    d("02:00:00:00:00:11", "192.168.1.21", { hostname: "Sams-iPhone", type: "phone", is_known: true, name: "Sam's phone" }, 3),
    d("02:00:00:00:00:12", "192.168.1.30", { vendor: "Roku, Inc", hostname: "LivingRoomRoku", type: "tv" }, 2),
    d("02:00:00:00:00:13", "192.168.1.31", { vendor: "Ring LLC", type: "camera", name: "Front door", is_known: true }, 0),
    d("02:00:00:00:00:14", "192.168.1.40", { vendor: "Amazon Technologies Inc.", type: "iot" }, 4, 30),
    d("02:00:00:00:00:15", "192.168.1.41", { vendor: "Shenzhen Intellirocks Tech. Co. Ltd.", type: "iot" }, 5, 9),
    d("02:00:00:00:00:16", "192.168.1.50", { hostname: "printer-office", vendor: "Seiko Epson Corporation", type: "printer", is_known: true, name: "Office printer" }, 300),
    d("02:00:00:00:00:17", "192.168.1.60", { type: "unknown" }, 1, 3),
    d("02:00:00:00:00:18", "192.168.1.61", { hostname: "xbox", type: "console" }, 60 * 26),
  ];
}

function seedEvents(): NetEvent[] {
  const e = (id: number, min: number, kind: NetEvent["kind"], severity: NetEvent["severity"],
    message: string, mac: string | null, data: Record<string, unknown> = {}): NetEvent =>
    ({ id, ts: minutesAgo(min), kind, severity, message, mac, data });
  return [
    e(9, 3, "new_device", "medium", "New device on your network: Unknown device at 192.168.1.60", "02:00:00:00:00:17", { ip: "192.168.1.60" }),
    e(8, 20, "joined", "info", "Sam's phone joined at 192.168.1.21", "02:00:00:00:00:11"),
    e(7, 45, "alert", "high", "Unknown device probed 24 ports on Family laptop in under a minute (possible port scan)", "02:00:00:00:00:17", { rule: "port_scan" }),
    e(6, 300, "left", "info", "Office printer left", "02:00:00:00:00:16"),
    e(5, 60 * 8, "ip_changed", "info", "Sam's phone changed IP 192.168.1.22 → 192.168.1.21", "02:00:00:00:00:11"),
    e(4, 60 * 26, "left", "info", "xbox left", "02:00:00:00:00:18"),
    e(3, 60 * 30, "joined", "low", "Roku device is back after 9 days at 192.168.1.30", "02:00:00:00:00:12", { days_away: 9 }),
    e(2, 60 * 24 * 3, "mac_conflict", "high", "Unknown device and Family laptop are both using 192.168.1.20", "02:00:00:00:00:17"),
    e(1, 60 * 24 * 12, "new_device", "info", "First scan found 9 devices. Review them and mark the ones you recognise as known.", null, { baseline: true, count: 9 }),
  ];
}

const IDLE: IdentifyStatus = {
  running: false, started_at: null, ends_at: null, done: 0, total: 0, current: null, port_check: false,
};

const clue = (source: EvidenceItem["source"], key: string, value: string): EvidenceItem =>
  ({ source, key, value, confidence: 1, last_seen: minutesAgo(0) });

/** What a simulated Identify run "learns" about some of the fake devices. */
const LEARNED: Record<string, Pick<Device, "model" | "os" | "suggested_name" | "type"> & { evidence: EvidenceItem[] }> = {
  "02:00:00:00:00:12": {
    type: "tv", model: "Roku Ultra", os: null, suggested_name: "Living Room Roku",
    evidence: [clue("upnp", "friendlyName", "Living Room Roku"), clue("upnp", "modelName", "Roku Ultra"),
      clue("upnp", "manufacturer", "Roku"), clue("ssdp", "server", "Roku/12.5.0 UPnP/1.0")],
  },
  "02:00:00:00:00:14": {
    type: "speaker", model: "Echo Dot", os: null, suggested_name: "Kitchen Echo",
    evidence: [clue("mdns", "service:_spotify-connect._tcp", "_spotify-connect._tcp"),
      clue("mdns", "txt:fn", "Kitchen Echo"), clue("mdns", "txt:md", "Echo Dot")],
  },
  "02:00:00:00:00:17": {
    type: "phone", model: null, os: "Android 14", suggested_name: null,
    evidence: [clue("dhcp", "vendor_class", "android-dhcp-14")],
  },
};

const state = {
  devices: seedDevices(),
  events: seedEvents(),
  capturing: true,
  settings: {
    offline_timeout_s: 600, sweep_interval_s: 300, retention_days: 30, lan_exposure: false, anomaly_plugin: false,
    port_check: false, identify_minutes: 10,
  } as Settings,
  identify: { ...IDLE },
  evidence: {} as Record<string, EvidenceItem[]>,
  timer: undefined as ReturnType<typeof setInterval> | undefined,
};

function finishIdentify(targets: Device[], reason: string | null) {
  clearInterval(state.timer);
  const learned = targets.filter((d) => LEARNED[d.mac] && state.identify.done > targets.indexOf(d));
  for (const device of learned) {
    const { evidence, ...identity } = LEARNED[device.mac];
    Object.assign(device, identity);
    state.evidence[device.mac] = evidence;
  }
  const examples = learned.map((d) => d.model ?? d.suggested_name).filter(Boolean).join(", ");
  state.events.unshift({
    id: Math.max(0, ...state.events.map((e) => e.id)) + 1,
    ts: minutesAgo(0), kind: "identified", severity: "info", mac: null,
    message: `Identify finished: learned more about ${learned.length} of ${targets.length} devices`
      + (examples ? ` (${examples}).` : ".") + (reason ? ` It ended early because ${reason}.` : ""),
    data: { total: targets.length, checked: state.identify.done, reason },
  });
  state.identify = { ...IDLE };
}

const delay = <T,>(value: T): Promise<T> => new Promise((r) => setTimeout(() => r(structuredClone(value)), 120));

const find = (mac: string): Device => {
  const device = state.devices.find((d) => d.mac === mac.toLowerCase());
  if (!device) throw new ApiError(404, "not_found", "No such device.");
  return device;
};

function summary(): Summary {
  const online = state.devices.filter((d) => d.online).length;
  return {
    online,
    offline: state.devices.length - online,
    unknown: state.devices.filter((d) => !d.is_known).length,
    total: state.devices.length,
    last_update: minutesAgo(0),
  };
}

function presence(device: Device): DeviceDetail["presence"] {
  const sessions: DeviceDetail["presence"] = [];
  for (let day = 6; day >= 0; day--) {
    const start = day * 1440 + 60 * (7 + (day % 3));
    const end = start - 60 * (4 + (day % 4));
    sessions.push({ start: minutesAgo(start), end: day === 0 && device.online ? null : minutesAgo(Math.max(end, 0)) });
  }
  return sessions;
}

export const mockApi: Api = {
  health: () => delay({ status: "ok", version: "mock", capturing: state.capturing, interface: "Wi-Fi" }),
  summary: () => delay(summary()),
  devices: (query = {}) => delay(state.devices.filter((d) =>
    (query.status === "online" ? d.online : query.status === "offline" ? !d.online : true)
    && (query.known === undefined || d.is_known === query.known))),
  device: async (mac) => {
    const device = find(mac);
    return delay({
      ...device,
      top_domains: [
        { domain: "time.example.com", count: 412, last_seen: minutesAgo(1) },
        { domain: "updates.example.net", count: 96, last_seen: minutesAgo(30) },
        { domain: "api.example.org", count: 41, last_seen: minutesAgo(5) },
      ],
      top_destinations: [
        { address: "203.0.113.10", port: 443, count: 220, last_seen: minutesAgo(1) },
        { address: "198.51.100.7", port: 123, count: 48, last_seen: minutesAgo(12) },
      ],
      presence: presence(device),
      evidence: state.evidence[device.mac] ?? [],
      suggestion: device.model || device.suggested_name || device.os
        ? { name: device.suggested_name, model: device.model, os: device.os, type: device.type }
        : null,
    });
  },
  updateDevice: async (mac, patch) => {
    const device = find(mac);
    if (patch.name !== undefined) device.name = patch.name?.trim() || null;
    if (patch.is_known !== undefined) device.is_known = patch.is_known;
    if (patch.notes !== undefined) device.notes = patch.notes?.trim() || null;
    return delay(device);
  },
  forgetDevice: async (mac) => {
    find(mac);
    state.devices = state.devices.filter((d) => d.mac !== mac.toLowerCase());
    state.events = state.events.filter((e) => e.mac !== mac.toLowerCase());
    await delay(null);
  },
  events: (query = {}) => delay(state.events
    .filter((e) => (query.since === undefined || e.id > query.since)
      && (!query.kind || e.kind === query.kind)
      && (!query.mac || e.mac === query.mac))
    .slice(0, query.limit ?? 100)),
  pause: () => {
    state.capturing = false;
    return mockApi.health();
  },
  resume: () => {
    state.capturing = true;
    return mockApi.health();
  },
  settings: () => delay(state.settings),
  updateSettings: async (patch) => {
    state.settings = { ...state.settings, ...patch };
    return delay(state.settings);
  },
  identify: () => delay(state.identify),
  startIdentify: async (options = {}) => {
    if (state.identify.running) throw new ApiError(409, "already_running", "Identify mode is already running.");
    if (!state.capturing) throw new ApiError(423, "monitoring_paused", "Resume monitoring before identifying devices.");
    const minutes = options.minutes ?? state.settings.identify_minutes;
    const targets = state.devices.filter((d) => d.online && (!options.macs || options.macs.includes(d.mac)));
    const started = new Date();
    state.identify = {
      running: true, started_at: started.toISOString(), ends_at: new Date(started.getTime() + minutes * 60_000).toISOString(),
      done: 0, total: targets.length, current: "Asking devices to describe themselves", port_check: state.settings.port_check,
    };
    state.timer = setInterval(() => {
      if (state.identify.done >= targets.length) return finishIdentify(targets, null);
      state.identify = { ...state.identify, current: targets[state.identify.done].ips[0] ?? null, done: state.identify.done + 1 };
    }, 700);
    return delay(state.identify);
  },
  stopIdentify: async () => {
    if (state.identify.running) {
      const targets = state.devices.filter((d) => d.online);
      finishIdentify(targets, "it was stopped");
    }
    return delay(state.identify);
  },
  exportUrl: "data:application/json,[]",
  streamUrl: null,
};
