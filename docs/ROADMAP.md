# NetSleuth roadmap

Written 2026-11-21. These are design notes, not commitments. The order of work is at the bottom.

## Gaps

1. **No network identity.** The backend watches whatever network the PC is on and writes everything into one `devices.db`. On someone else's network (school, work, a café) it:
   - ARP-sweeps up to a /22 every 5 minutes, which many acceptable-use policies forbid and intrusion detection flags;
   - fills the home inventory with strangers and raises new-device and conflict alerts about them.
2. **The Identify branch isn't merged.** It's waiting for a live run at home. The live database is already schema v2, so new schema work has to build on that branch.
3. **No way to test without a live network.** `npm run dev:mock` covers only the dashboard.
4. **Dead ML code.** `backend/netsleuth/ml` isn't wired in, and an IsolationForest can't explain its results.
5. **`lan_exposure` has no authentication.** Turning it on exposes writes (DELETE, settings) to the whole LAN.

---

## 1. Network profiles

**Recognising a network**
- `network_id = hash(gateway MAC + subnet)`.
- The gateway MAC comes from the OS ARP cache (`Get-NetNeighbor`), so finding it sends no packets.
- The SSID (`netsh wlan show interfaces`) and the DHCP domain are kept as labels only, because they're easy to spoof or reuse.

**Trust levels**

| Trust | Capture | ARP sweep | Identify | Alerts / notifications |
|---|---|---|---|---|
| `home` | yes | yes | yes | yes |
| `observe` | passive only | no | no | in the log only, no toasts |
| `idle` (the default for a new network) | no | no | no | no |

**Storage**
- One database per network: `networks/<id>/devices.db`, plus a `networks.json` index.
- `DeviceStore` doesn't change, networks are fully isolated, and forgetting one means deleting a folder.
- The existing database is offered on the dashboard and moved only when the user chooses. (An automatic match by router was tried and adopted the list into a friend's network: same 10.0.0.0/24, router at .1.)

**Switching** (built)
- The backend fingerprints the network itself at start-up and rechecks every 15 s. When the network changes, it exits with code 5 and the tray restarts it at once, on the new network's profile. No `--network` flag is needed.
- On a network it hasn't seen before, the backend starts idle and serves only the dashboard.

**API**
- `GET /network` returns `{id, label, ssid, subnet, trust}`.
- `PATCH /network` takes `{label?, trust?}`.
- `GET /networks` lists the known networks.
- `DELETE /networks/{id}` forgets a network.
- `Health` gains `network` and `trust`.

**Dashboard and tray**
- The dashboard shows a banner on a network it doesn't know ("NetSleuth is idle here"), with buttons for **Monitor this network** and **Stay idle**.
- The tray icon turns grey for "Idle: not your network".

## 2. Offline testing: replay mode

- `python -m netsleuth --replay FILE.pcap` feeds the pipeline from a capture file instead of Npcap.
  - It sends nothing: no ARP sweep, and no Identify probes.
  - The dashboard and API run as usual, so a replay also works as a demo.
- **Scenario fixtures** are generated with scapy from invented MACs and IPs (`backend/tests/scenarios.py`):
  - first run
  - DHCP hostnames
  - mDNS and UPnP clues
  - gateway ARP spoofing
  - port scan
  - host sweep
- **Later:** fake SSDP and mDNS responders on loopback, so Identify mode can be tested from start to finish.

## 3. Later

- **Behaviour baselines in place of the ML code.** Each alert explains itself, for example:
  - "first time this device used port X"
  - "contacting many more destinations than usual"
  - "active at an unusual hour"

  Then delete `ml/`.
- **Watch list.** Notify when a chosen device leaves or comes back.
- **LAN token.** Required whenever the dashboard is bound to anything other than localhost. It's generated on first enable and shown once as a QR code.

### Status of network profiles

- **Step 1 (backend), done:** fingerprinting, the registry, a database per network, trust gates, the change watcher with exit code 5, the `/network` and `/networks` API, the look-alike alert, and an immediate tray restart on code 5.
- **Confirm-first setup, done:** nothing is recorded on a network until the user chooses. The dashboard's setup view shows how the network was recognised, offers the earlier device list (with a "recorded on this router" hint), and asks Home, Observe or Idle. Adoption goes through `POST /network/legacy/adopt` and a restart.
- **Step 3 (dashboard), partly done:** the setup view, the Networks page (rename, change trust, forget), and the header badge (Idle / Listening / Watching).
- **Step 2 (tray):** a grey icon while idle, no notifications on Observe or Idle networks, and the trust level in the tooltip and menu.
- **Step 3, remaining:** a cleanup for devices from other networks that are already in the earlier list. They can share the home subnet, so it must sort them by router and time, not by address.
- **Later:** a "same network, new router" action that links the new router to the existing Home inventory instead of starting a fresh one.

## Order of work

1. Replay harness and scenario fixtures.
2. Live Identify run at home, tune, then merge `feature/device-identification`.
3. Network profiles: backend, then tray, then dashboard. Test with replay, including a network-switch scenario, then live.
4. Baselines, watch list and LAN token, in any order.
