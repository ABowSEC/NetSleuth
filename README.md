# NetSleuth

NetSleuth keeps an inventory of what's on your home network. It shows which devices are home right now, which ones are new, and when each one arrived and left. It also warns you about the few things worth knowing, such as another device claiming your router's address or a device probing others on your network.

It runs on one Windows PC, watches the network that PC is connected to, and shows a dashboard at `http://localhost:5000`. Nothing leaves your machine.

## What you get

- **A device inventory keyed by MAC address.** Each device has:
  - a maker (from its MAC prefix)
  - a best-guess type
  - its hostname (from DHCP or mDNS)
  - its IP history
  - whether it's here now or away
- **"Haven't met these yet".** Unrecognised devices are listed at the top. Type a name and press Enter, and the device moves into your known list, so the next stranger stands out.
- **Activity log.** Arrivals, departures, IP changes and new devices.
  - **Security alerts:**
    - an IP address claimed by two devices at once (critical if it's the router's)
    - one device opening many ports on another
    - one device contacting many devices on the same port
  - When you first run NetSleuth, the devices it finds are summarised as a single event instead of one alert per device.
- **Per-device detail:**
  - a 7-day online timeline
  - the domains it looks up most
  - the addresses it connects to most
- **A tray icon** with live status, desktop notifications for new devices, pause/resume, and start with Windows.

## Requirements

- Windows 10 or 11
- [Python 3.11+](https://www.python.org/downloads/) on your `PATH`
- [Node.js 20.9+](https://nodejs.org/), to build the dashboard once
- [Npcap](https://npcap.com), installed with the default options

Administrator rights aren't needed. If Npcap was installed with *"Restrict Npcap driver's access to Administrators only"*, either reinstall it without that option or run NetSleuth as administrator.

## Setup and running

From a normal terminal in the repo folder:

```
setup.bat
```

This creates `.venv`, installs the backend and the tray, and builds the dashboard into `frontend/out`. Run it again after pulling updates.

Then start NetSleuth:

```
run.bat
```

A magnifying-glass icon appears in the notification area. Its colour shows the state:

| Colour | Meaning |
|---|---|
| Green | Running |
| Amber | Starting, paused, or there are devices you haven't recognised |
| Red | Something needs your attention. Hover over the icon or open the menu to see what. |

Click the icon to open the dashboard. The first network sweep runs a few seconds after start-up.

### Without the tray

```
.venv\Scripts\python -m netsleuth -i "Wi-Fi"
```

Useful flags:

| Flag | Effect |
|---|---|
| `--port 5050` | Use a different port |
| `--host 0.0.0.0` | Let other devices on your network open the dashboard |
| `--verbose` | Debug logging |
| `--dev` | Accept writes from the Next.js dev server on `localhost:3000` |

Stop it with Ctrl+C.

## Settings

Change these on the dashboard's **Settings** page, or in `%LOCALAPPDATA%\NetSleuth\config.toml`:

| Setting | Default | Meaning |
|---|---|---|
| `offline_timeout_s` | 600 | Silence before a device counts as away |
| `sweep_interval_s` | 300 | How often the ARP sweep looks for quiet devices |
| `retention_days` | 30 | Activity and traffic history older than this is deleted. Devices are kept. |
| `lan_exposure` | false | Bind the dashboard to all interfaces (applies after a restart) |

To override any setting for a single run, set an environment variable of the form `NETSLEUTH_<SETTING>`, for example `NETSLEUTH_SWEEP_INTERVAL_S=60`.

The tray's own preferences (interface, port, notifications) are in `tray.json`.

## Where things are stored

Everything is under `%LOCALAPPDATA%\NetSleuth`. Set `NETSLEUTH_HOME` to move it.

| Path | Contents |
|---|---|
| `devices.db` | SQLite database: devices, IP history, presence, activity, traffic counts |
| `config.toml`, `tray.json` | Settings |
| `logs\` | `netsleuth.log` / `backend.log`, `backend-stderr.log`, `tray.log` |
| `run\` | `backend.pid`, `tray.lock` |

## Troubleshooting

| Symptom | What to do |
|---|---|
| Tray turns red: "Windows refused packet capture" | Npcap is admin-only. Reinstall it without that restriction, or run as administrator. |
| "Port 5000 is already in use" | Something else is listening there. Close it, or set `"port"` in `tray.json`. |
| No devices appear | Check that the tray is watching the right interface: **Network interface** in the menu. |
| Dashboard says "Can't reach NetSleuth" | The backend isn't running. Use **Restart NetSleuth** in the tray menu, and check `logs\backend.log`. |
| A device has no maker | Phones and tablets use private (randomised) Wi-Fi addresses with no maker prefix. The device drawer explains how to match one up. |

## How it works

```
Npcap capture ──► pipeline worker ──► DeviceStore (memory + SQLite)
ARP sweep ─────►        │                    │
                        ▼                    ▼
                   EventEngine ──► events ──► Flask/waitress API ──► dashboard (static Next.js)
                                                     ▲
                                         tray supervisor (start, health, restart, stop)
```

- **Capture.** `backend/netsleuth/core/capture.py` only queues packets.
  - `packets.py` turns them into facts: sightings, hostnames, DNS queries, flows. An IP is attached to a device only if it's inside your subnet.
  - `pipeline.py` applies those facts on a worker thread.
  - `discovery.py` runs ARP sweeps to find quiet devices.
- **Storage.** `core/store.py` keeps state in memory and batches writes to SQLite every 2 seconds. The database uses WAL and versioned migrations.
- **Events.** `core/events.py` turns sightings into joined, left and new-device events, plus alerts. The API serves them, and `/api/v1/stream` pushes them live.
- **API.** Documented in [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md). It accepts writes only as same-origin JSON.
- **Dashboard.** `frontend/` is Next.js 16, exported as static files that the backend serves. See [`frontend/README.md`](frontend/README.md).
- **Tray.** `tray/` supervises the backend. See [`tray/README.md`](tray/README.md).

## Development

```
cd backend   && python -m pytest       # backend
python -m pytest tray                  # tray supervisor (run from repo root)
cd frontend  && npm run check          # types, lint, unit tests
cd frontend  && npm run dev:mock       # dashboard with fake data, no backend
```

To work on the dashboard against a real backend, run `python -m netsleuth --dev` and `npm run dev`, then open `localhost:3000`.
