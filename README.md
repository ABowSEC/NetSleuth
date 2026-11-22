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

## Networks

NetSleuth keeps a separate device list for each network your PC joins, so devices at school, work or a café never mix with your home list. It recognises a network by its router (the router's hardware address plus the subnet). The Wi-Fi name is shown as a label, but on its own it isn't trusted, because names repeat and anyone can copy yours.

Each network has a trust level:

| Trust | What NetSleuth does there |
|---|---|
| Home | Everything: listening, network sweeps, Identify, alerts and notifications |
| Observe | Listens only. No sweeps, no Identify. |
| Idle | Nothing. This is where every new network starts. |

On a network it hasn't met, NetSleuth records nothing and the dashboard opens on a setup view instead. It shows how it recognised the network (Wi-Fi name, address range, router) and asks what NetSleuth may do there: **Home**, **Observe** or **Idle**. If you used NetSleuth before network profiles, the setup view also offers your earlier device list. It says whether that list was recorded on this network's router, but it's only moved when you choose it. Many networks look alike (a friend's router can use the same 10.0.0.x addresses as yours), so NetSleuth never guesses.

The **Networks** page lists every network the PC has joined. You can rename each one, change its trust level, or forget it along with its device list.

To start over completely, use **Reset NetSleuth** at the bottom of **Settings**. It deletes every network and device list, including names, notes, history and activity. Your settings and logs are kept. NetSleuth restarts to do it, and the network you're on comes back as new and idle. If the dashboard won't open, you can do the same by hand: quit NetSleuth, create an empty file named `reset-pending` in `%LOCALAPPDATA%\NetSleuth`, then start it again.

When the PC moves to another network, NetSleuth switches to that network's list within about 15 seconds.

If a new network has the same Wi-Fi name and subnet as your Home network but a different router, NetSleuth stays idle and raises an alert. If you replaced your router, set the new one to Home. If you didn't, another device may be imitating your network.

## Where things are stored

Everything is under `%LOCALAPPDATA%\NetSleuth`. Set `NETSLEUTH_HOME` to move it.

| Path | Contents |
|---|---|
| `networks.json` | The networks NetSleuth knows, with their trust levels |
| `networks\<id>\devices.db` | One SQLite database per network: devices, IP history, presence, activity, traffic counts |
| `replay\devices.db` | Throwaway database for replay mode |
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
| A Wi-Fi network shows no name | Windows only shares the Wi-Fi name with apps when Location services are on (Settings → Privacy & security → Location, "Let desktop apps access your location"). NetSleuth still tells networks apart by their router. |
| The dashboard shows "New network" | NetSleuth hasn't been told about this network yet, so it's recording nothing. Choose Home, Observe or Idle (see **Networks**). |
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
                                       # set NEXT_PUBLIC_MOCK_SCENARIO=new-network to start on an unknown network
```

To work on the dashboard against a real backend, run `python -m netsleuth --dev` and `npm run dev`, then open `localhost:3000`.

### Replay mode (no live network)

Replay mode runs the pipeline, events and dashboard on a capture file in place of live capture. It sends no packets: there is no ARP sweep and no Identify. It writes to its own throwaway database (`replay\devices.db`, which is wiped at the start of each replay), so your real inventory is never touched.

Generate the built-in scenarios (invented devices on `192.168.77.0/24`):

```
python -m netsleuth.scenarios scenarios
```

That writes `baseline`, `new_device`, `gateway_spoof`, `port_scan` and `host_sweep` captures. Replay one:

```
python -m netsleuth --replay scenarios\port_scan.pcap --gateway 192.168.77.1
```

| Flag | Effect |
|---|---|
| `--replay-speed N` | `0` as fast as possible (the default), `1` original pacing, `10` ten times faster. Gaps longer than 5 s are cut short. |
| `--replay-exit` | Exit when the file ends. Without it, the dashboard keeps running until Ctrl+C. |
| `--subnet CIDR` | The capture's LAN. By default it's inferred from the most common private address. |
| `--gateway IP` | The router's IP. Needed for router-takeover alerts. |

Alert windows and the first-run summary follow the capture's own timestamps, so a fast replay raises the same alerts as the original traffic. Stored first-seen and last-seen times are still wall-clock times.
