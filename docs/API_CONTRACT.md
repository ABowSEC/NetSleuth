# NetSleuth API Contract — v1

This is the shared contract between the three refactor branches:

| Branch | Role |
|---|---|
| `refactor/backend` | **Implements** this contract |
| `refactor/ui` | **Consumes** the HTTP API (develops against fixtures until backend merges) |
| `refactor/process` | **Consumes** the CLI + health/summary/capture endpoints |

Changes to this file must land on all three branches (or on the base before branching).

---

## Conventions

- Base path: `/api/v1`
- Default bind: `127.0.0.1:5000`. LAN exposure is opt-in (`--host 0.0.0.0` or setting `lan_exposure`).
- All timestamps: ISO-8601 UTC with `Z` suffix, e.g. `2026-10-30T14:03:22Z`. Never `"Unknown"` — use `null`.
- MAC addresses: lowercase, colon-separated (`aa:bb:cc:dd:ee:ff`). URL path segments carry the MAC as-is.
- Write requests (`POST`/`PATCH`/`DELETE`) **must** send `Content-Type: application/json` (an empty body is `{}`). Requests with another content type → `415`.
- Write requests with an `Origin` header that isn't same-origin → `403` (dev mode additionally allows `http://localhost:3000`).
- Errors: `{"error": "<code>", "message": "<human text>"}` with an appropriate 4xx/5xx status.

---

## Types

```ts
type DeviceType =
  | "router" | "computer" | "phone" | "tablet" | "tv" | "speaker"
  | "camera" | "printer" | "console" | "iot" | "unknown";

interface Device {
  mac: string;                 // primary identity
  name: string | null;         // user-assigned
  hostname: string | null;     // DHCP / mDNS / NetBIOS
  vendor: string | null;       // OUI lookup
  type: DeviceType;
  is_known: boolean;
  online: boolean;
  ips: string[];               // current first, then history (most recent first)
  first_seen: string;          // ISO UTC
  last_seen: string;           // ISO UTC
  notes: string | null;
  // Identification (derived from evidence; null when unknown)
  model: string | null;          // e.g. "Roku Ultra", "MacBook Pro"
  os: string | null;             // e.g. "Android 14", "Windows"
  suggested_name: string | null; // best name the device gave itself, offered to the user
}

type EvidenceSource = "upnp" | "roku" | "mdns" | "netbios" | "rdns" | "dhcp" | "ssdp" | "ports";

interface EvidenceItem {
  source: EvidenceSource;
  key: string;                   // e.g. "modelName", "txt:md", "service:_googlecast._tcp", "vendor_class"
  value: string;
  confidence: number;            // 0..1
  last_seen: string;             // ISO UTC
}

interface DeviceDetail extends Device {
  top_domains: { domain: string; count: number; last_seen: string }[];
  top_destinations: { address: string; port: number | null; count: number; last_seen: string }[];
  presence: { start: string; end: string | null }[];   // last 7 days of online sessions
  evidence: EvidenceItem[];      // strongest source first
  suggestion: { name: string | null; model: string | null; os: string | null; type: DeviceType } | null;
}

type EventKind = "joined" | "left" | "new_device" | "ip_changed" | "mac_conflict" | "alert" | "identified";
type Severity = "info" | "low" | "medium" | "high" | "critical";

interface Event {
  id: number;                  // monotonically increasing
  ts: string;                  // ISO UTC
  kind: EventKind;
  mac: string | null;
  severity: Severity;
  message: string;
  data: Record<string, unknown>;
}

interface Summary {
  online: number;
  offline: number;
  unknown: number;             // devices with is_known=false
  total: number;
  last_update: string;         // ISO UTC
}

interface Health {
  status: "ok";
  version: string;
  capturing: boolean;          // false while paused, or while this network is idle
  interface: string | null;
  started_at: string;          // ISO UTC; when this backend process started (changes on every restart)
  network: { id: string; label: string | null; ssid: string | null; trust: Trust } | null;  // null in replay mode
}

// Network profiles: each network keeps its own inventory. A network is identified by its
// router (gateway MAC + subnet); the SSID is a label and a supporting clue only.
type Trust =
  | "home"      // capture, ARP sweep, Identify, alerts and notifications
  | "observe"   // passive capture only: no sweep, no Identify
  | "idle";     // nothing is captured. Every new network starts here.

interface Network {
  id: string;                  // 12 hex chars
  label: string | null;        // user-assigned
  ssid: string | null;         // null on Ethernet, or when Windows withholds it (Location services off)
  subnet: string;              // e.g. "10.0.0.0/24"
  gateway_ip: string | null;
  gateway_mac: string | null;
  trust: Trust;
  first_seen: string;          // ISO UTC
  last_seen: string;           // ISO UTC
  similar_to: string | null;   // id of a known network with the same SSID and subnet but another router
  current: boolean;            // the network this PC is on now
}

// The device list recorded before network profiles (<data dir>/devices.db), offered to the current network.
// It is never moved automatically: networks can look identical except for the router.
interface LegacyList {
  available: boolean;          // false once adopted, or if there is none
  devices: number;
  last_seen: string | null;    // ISO UTC
  likely_here: boolean;        // its first recorded router is this network's router (a hint only)
  adoptable: boolean;          // false once this network has devices or events of its own
}

interface Settings {
  offline_timeout_s: number;   // default 600
  sweep_interval_s: number;    // default 300; ARP sweep
  retention_days: number;      // default 30; events + counts
  lan_exposure: boolean;       // default false; takes effect on restart
  anomaly_plugin: boolean;     // default false
  port_check: boolean;         // default false; Identify mode also checks 13 common TCP ports per device
  identify_minutes: number;    // default 10; 5..30; longest an Identify run may take
}

// Identify mode: active probing that only runs when started, then switches itself off.
interface IdentifyStatus {
  running: boolean;
  started_at: string | null;   // ISO UTC
  ends_at: string | null;      // ISO UTC; the run stops by itself at this time at the latest
  done: number;                // devices checked so far
  total: number;               // devices in this run
  current: string | null;      // what it is doing now (an IP, or a step description)
  port_check: boolean;         // whether this run includes the port check
}
```

---

## Endpoints

| Method | Path | Body | Response |
|---|---|---|---|
| GET | `/health` | — | `Health` |
| GET | `/summary` | — | `Summary` |
| GET | `/devices` | query: `status=online\|offline\|all` (default all), `known=true\|false`, `q=<search>` | `Device[]` |
| GET | `/devices/{mac}` | — | `DeviceDetail` or 404 |
| PATCH | `/devices/{mac}` | `{ name?: string\|null, is_known?: boolean, notes?: string\|null }` | `Device` |
| DELETE | `/devices/{mac}` | `{}` | `204` — forgets device and its history |
| GET | `/events` | query: `since=<id>`, `limit` (default 100, max 1000), `kind`, `mac` | `Event[]` newest first |
| GET | `/events/export` | — | `Event[]` as a JSON download (`Content-Disposition: attachment`) |
| GET | `/stream` | — | Server-Sent Events (see below) |
| POST | `/capture/pause` | `{}` | `Health` |
| POST | `/capture/resume` | `{}` | `Health` |
| GET | `/settings` | — | `Settings` |
| PATCH | `/settings` | `Partial<Settings>` | `Settings` |
| GET | `/identify` | — | `IdentifyStatus` |
| POST | `/identify/start` | `{ minutes?: 1..30, macs?: string[] }` (default: `identify_minutes`; online devices not checked in the last hour) | `IdentifyStatus`; `409` already running, `423` monitoring paused (`monitoring_paused`) or this network isn't Home (`network_not_home`) |
| POST | `/identify/stop` | `{}` | `IdentifyStatus` |
| GET | `/network` | — | `Network` (the current one); `404` in replay mode |
| PATCH | `/network` | `{ label?: string\|null, trust?: Trust }` | `Network`. Trust takes effect at once. |
| GET | `/network/legacy` | — | `LegacyList` for the current network; `404` in replay mode |
| POST | `/network/legacy/adopt` | `{ trust?: "home"\|"observe" }` (default home) | `202 {restarting: true}`: the backend restarts (exit `5`) and moves the list into this network on start-up. `409` `nothing_to_adopt` or `network_has_data`. |
| POST | `/reset` | `{ confirm: "reset" }` | `202 {restarting: true}`: deletes every network and device list (including the pre-profiles one) on the restart that follows. Settings and logs are kept. `400` without the confirmation; `404` in replay mode. |
| GET | `/networks` | — | `Network[]`, most recently seen first (`[]` in replay mode) |
| PATCH | `/networks/{id}` | `{ label?: string\|null, trust?: Trust }` | `Network` or 404 |
| DELETE | `/networks/{id}` | `{}` | `204`: forgets the network and deletes its inventory. `409` for the current network. |

### `/stream` (SSE)

- `event: event` — `data: Event` (one per new event)
- `event: summary` — `data: Summary` (on change, at most every 2 s)
- `event: identify` — `data: IdentifyStatus` (progress while a run is active; a final frame has `running: false`)
- `: ping` comment every 15 s (heartbeat)
- Clients reconnect with `Last-Event-ID` = last `Event.id` to resume.

---

## Backend CLI (consumed by the tray supervisor)

```
python -m netsleuth [--interface NAME] [--host 127.0.0.1] [--port 5000]
                    [--headless] [--dev] [--log-file PATH] [--exit-on-stdin-close]
                    [--replay FILE [--replay-speed N] [--replay-exit] [--subnet CIDR] [--gateway IP]]
```

- `--replay FILE`: offline testing. Reads a .pcap instead of capturing, sends nothing, and writes to `<data dir>/replay/devices.db` (wiped at start). There's no Identify mode: `/identify/start` returns `503`. `Health.interface` is `"replay:<file name>"`. A missing or unreadable file, an undetectable subnet, or a gateway outside the subnet exits with `2`.

- `--headless`: no interactive prompts; fails with exit code `2` if `--interface` is missing and more than one candidate exists.
- `--dev`: allows `http://localhost:3000` origin for writes.
- Exit codes: `0` clean shutdown, `2` usage/config error, `3` capture permission denied (e.g. Npcap installed admin-only), `4` port in use, `5` restart to switch network profiles (the PC moved to another network, the user chose to adopt the earlier device list, or asked for a reset; restart at once, not a crash), `1` other.
- Network profiles: at start-up the backend fingerprints the network (router MAC from the OS ARP cache, SSID from `netsh wlan`; nothing is sent), opens that network's inventory (`<data dir>/networks/<id>/devices.db`, indexed in `networks.json`) and behaves according to its trust. It rechecks every 15 s and exits with `5` when the network changes. The pre-profiles `<data dir>/devices.db` stays where it is until the user adopts it into a network from the dashboard (`POST /network/legacy/adopt`).
- Graceful shutdown (stop capture, flush DB writer, exit `0` within 5 s) on any of:
  - `SIGINT`/`SIGTERM`, or `CTRL_BREAK_EVENT` from a process sharing the backend's console;
  - **stdin reaching EOF, when started with `--exit-on-stdin-close`.** This is how the tray stops the backend: it runs without a console (pythonw), so it can't send Ctrl+Break. It keeps a pipe to the backend's stdin and closes it. If the tray dies, the pipe closes too, so the backend is never orphaned.
- Ready signal: `GET /api/v1/health` returns 200.
