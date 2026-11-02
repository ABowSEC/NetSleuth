import {
  toDeviceDetail, toDevice, toDevices, toEvents, toHealth, toIdentify, toSettings, toSummary,
} from "./guards";
import { ApiError } from "./errors";
import { mockApi } from "./mock";
import type {
  Device, DeviceDetail, DevicePatch, EventKind, Health, IdentifyStatus, NetEvent, Settings, Summary,
} from "./types";

export { ApiError };

const BASE = "/api/v1";

async function request(path: string, init?: RequestInit): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...init,
      headers: init?.body !== undefined || (init?.method && init.method !== "GET")
        ? { "Content-Type": "application/json", ...init?.headers }
        : init?.headers,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(0, "unreachable", "Can't reach NetSleuth. Is it running?");
  }
  if (res.status === 204) return null;
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const b = (body ?? {}) as { error?: string; message?: string };
    throw new ApiError(res.status, b.error ?? "http_error", b.message ?? `Request failed (${res.status})`);
  }
  return body;
}

const write = (method: string, path: string, data: unknown = {}) =>
  request(path, { method, body: JSON.stringify(data) });

export interface DeviceQuery {
  status?: "all" | "online" | "offline";
  known?: boolean;
  q?: string;
}

export interface EventQuery {
  since?: number;
  limit?: number;
  kind?: EventKind;
  mac?: string;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== "") search.set(key, String(value));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
}

export interface Api {
  health(): Promise<Health>;
  summary(): Promise<Summary>;
  devices(query?: DeviceQuery, signal?: AbortSignal): Promise<Device[]>;
  device(mac: string, signal?: AbortSignal): Promise<DeviceDetail>;
  updateDevice(mac: string, patch: DevicePatch): Promise<Device>;
  forgetDevice(mac: string): Promise<void>;
  events(query?: EventQuery, signal?: AbortSignal): Promise<NetEvent[]>;
  pause(): Promise<Health>;
  resume(): Promise<Health>;
  settings(): Promise<Settings>;
  updateSettings(patch: Partial<Settings>): Promise<Settings>;
  identify(): Promise<IdentifyStatus>;
  startIdentify(options?: { minutes?: number; macs?: string[] }): Promise<IdentifyStatus>;
  stopIdentify(): Promise<IdentifyStatus>;
  exportUrl: string;
  streamUrl: string | null;
}

const httpApi: Api = {
  health: async () => toHealth(await request("/health")),
  summary: async () => toSummary(await request("/summary")),
  devices: async (query = {}, signal) =>
    toDevices(await request(`/devices${qs({ status: query.status, known: query.known, q: query.q })}`, { signal })),
  device: async (mac, signal) => toDeviceDetail(await request(`/devices/${encodeURIComponent(mac)}`, { signal })),
  updateDevice: async (mac, patch) => toDevice(await write("PATCH", `/devices/${encodeURIComponent(mac)}`, patch)),
  forgetDevice: async (mac) => {
    await write("DELETE", `/devices/${encodeURIComponent(mac)}`);
  },
  events: async (query = {}, signal) =>
    toEvents(await request(`/events${qs({ ...query })}`, { signal })),
  pause: async () => toHealth(await write("POST", "/capture/pause")),
  resume: async () => toHealth(await write("POST", "/capture/resume")),
  settings: async () => toSettings(await request("/settings")),
  updateSettings: async (patch) => toSettings(await write("PATCH", "/settings", patch)),
  identify: async () => toIdentify(await request("/identify")),
  startIdentify: async (options = {}) => toIdentify(await write("POST", "/identify/start", options)),
  stopIdentify: async () => toIdentify(await write("POST", "/identify/stop")),
  exportUrl: `${BASE}/events/export`,
  streamUrl: `${BASE}/stream`,
};

export const api: Api = process.env.NEXT_PUBLIC_MOCK === "1" ? mockApi : httpApi;
