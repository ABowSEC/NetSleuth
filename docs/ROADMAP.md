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
| `ignore` (the default for a new network) | no | no | no | no |

**Storage**
- One database per network: `networks/<id>/devices.db`, plus a `networks.json` index.
- `DeviceStore` doesn't change, networks are fully isolated, and forgetting one means deleting a folder.
- The existing database is adopted as the first `home` network.

**Switching**
- The tray checks the default route and gateway every ~10 s. When they change, it restarts the backend with `--network <id>`.
- On a network it hasn't seen before, the backend starts in `ignore` mode and serves only the dashboard.

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

## Order of work

1. Replay harness and scenario fixtures.
2. Live Identify run at home, tune, then merge `feature/device-identification`.
3. Network profiles: backend, then tray, then dashboard. Test with replay, including a network-switch scenario, then live.
4. Baselines, watch list and LAN token, in any order.
