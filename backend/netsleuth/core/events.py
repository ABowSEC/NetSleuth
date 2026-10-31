"""Turns pipeline observations into persisted events and alerts.

Event kinds (see docs/API_CONTRACT.md): joined, left, new_device, ip_changed,
mac_conflict, alert. Each emitted event is stored and then published to
subscribers (the live stream).

Rules
- new_device: first sighting of a MAC that isn't known. On the very first
  run (empty event history) every device is new, so devices found during the
  start-up grace period are summarised in one event instead.
- joined / left: presence changes. ``joined`` is suppressed for a short grace
  period after start-up, when every device "comes online" at once.
- A device back after ``RETURNING_AFTER_DAYS`` gets a low-severity joined.
- ip_changed: a device moved to a new IP (usually a DHCP renewal).
- mac_conflict: an IP is claimed by a second MAC while its previous owner is
  still active (ARP spoofing indicator); critical when the IP is the gateway.
- alert/port_scan: one local device opens many ports on one local target.
- alert/host_sweep: one local device contacts many local hosts on one port.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict, deque
from datetime import timedelta
from typing import Callable

from ..timeutil import parse_iso, utcnow
from .packets import Flow
from .pipeline import PipelineObserver
from .store import Device, DeviceStore, Observation

log = logging.getLogger(__name__)

STARTUP_GRACE_S = 120
RETURNING_AFTER_DAYS = 7
CONFLICT_ACTIVE_S = 120        # previous owner seen this recently -> conflict
SCAN_WINDOW_S = 60
PORT_SCAN_THRESHOLD = 20       # distinct ports on one target within the window
HOST_SWEEP_THRESHOLD = 20      # distinct local hosts on one port within the window
ALERT_COOLDOWN_S = 600

Subscriber = Callable[[dict], None]


def label(device: Device | None, fallback: str) -> str:
    if not device:
        return fallback
    return device.name or device.hostname or (f"{device.vendor} device" if device.vendor else device.mac)


class EventEngine(PipelineObserver):
    def __init__(self, store: DeviceStore, gateway_ip: str | None = None,
                 clock: Callable[[], float] = time.monotonic, first_run: bool = False,
                 own_mac: str | None = None):
        self.store = store
        self.gateway_ip = gateway_ip
        # This computer. Its own traffic (including Identify mode's probes) never raises alerts.
        self.own_mac = own_mac
        self.first_run = first_run
        self._baseline: set[str] = set()
        self._baseline_reported = not first_run
        self._clock = clock
        self._started = clock()
        self._lock = threading.Lock()
        self._subscribers: list[Subscriber] = []
        self._cooldowns: dict[tuple, float] = {}
        self._flows: dict[str, deque] = defaultdict(deque)   # mac -> (t, target, port)

    # ── Publishing ───────────────────────────────────────────────────────────

    def subscribe(self, fn: Subscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subscribers:
                    self._subscribers.remove(fn)
        return unsubscribe

    def emit(self, kind: str, severity: str, message: str, mac: str | None = None, **data) -> dict:
        event = self.store.add_event(kind, severity, message, mac=mac, data=data)
        with self._lock:
            subscribers = list(self._subscribers)
        for fn in subscribers:
            try:
                fn(event)
            except Exception:
                log.exception("Event subscriber failed")
        log.info("[%s/%s] %s", kind, severity, message)
        return event

    def _cooled_down(self, key: tuple) -> bool:
        """True (and arms the cooldown) if ``key`` hasn't fired recently."""
        now = self._clock()
        with self._lock:
            last = self._cooldowns.get(key)
            if last is not None and now - last < ALERT_COOLDOWN_S:
                return False
            self._cooldowns[key] = now
            return True

    @property
    def in_grace(self) -> bool:
        return self._clock() - self._started < STARTUP_GRACE_S

    # ── Observer hooks ───────────────────────────────────────────────────────

    def on_sighting(self, mac: str, ip: str | None, obs: Observation) -> None:
        device = self.store.get(mac)
        name = label(device, mac)
        where = f" at {ip}" if ip else ""

        if obs.is_new:
            if device and device.is_known:
                pass
            elif self.first_run and self.in_grace:
                with self._lock:
                    self._baseline.add(mac)
            else:
                self.emit("new_device", "medium", f"New device on your network: {name}{where}", mac=mac, ip=ip)
        elif obs.came_online:
            away = self._days_away(obs.previous_last_seen)
            if away >= RETURNING_AFTER_DAYS:
                self.emit("joined", "low", f"{name} is back after {away} days{where}", mac=mac, ip=ip, days_away=away)
            elif not self.in_grace:
                self.emit("joined", "info", f"{name} joined{where}", mac=mac, ip=ip)

        if obs.previous_ip and ip and not obs.is_new:
            self.emit("ip_changed", "info", f"{name} changed IP {obs.previous_ip} → {ip}",
                      mac=mac, ip=ip, previous_ip=obs.previous_ip)

        if obs.ip_taken_from and ip:
            self._check_conflict(mac, ip, obs.ip_taken_from, name)

    def on_tick(self) -> None:
        if self._baseline_reported or self.in_grace:
            return
        self._baseline_reported = True
        with self._lock:
            found = len(self._baseline)
        if found:
            self.emit("new_device", "info",
                      f"First scan found {found} device{'s' if found != 1 else ''}. "
                      "Review them and mark the ones you recognise as known.",
                      baseline=True, count=found)

    def on_offline(self, devices: list[Device]) -> None:
        for device in devices:
            self.emit("left", "info", f"{label(device, device.mac)} left", mac=device.mac)

    def on_flow(self, flow: Flow) -> None:
        if not flow.local or flow.port is None or flow.mac == self.own_mac:
            return
        now = self._clock()
        with self._lock:
            window = self._flows[flow.mac]
            window.append((now, flow.address, flow.port))
            while window and now - window[0][0] > SCAN_WINDOW_S:
                window.popleft()
            ports_by_target: dict[str, set] = defaultdict(set)
            hosts_by_port: dict[int, set] = defaultdict(set)
            for _, target, port in window:
                ports_by_target[target].add(port)
                hosts_by_port[port].add(target)

        name = label(self.store.get(flow.mac), flow.mac)
        ports = ports_by_target[flow.address]
        if len(ports) >= PORT_SCAN_THRESHOLD and self._cooled_down(("port_scan", flow.mac, flow.address)):
            target = label(self.store.get(self.store.mac_for_ip(flow.address) or ""), flow.address)
            self.emit("alert", "high",
                      f"{name} probed {len(ports)} ports on {target} in under a minute (possible port scan)",
                      mac=flow.mac, rule="port_scan", target=flow.address, ports=sorted(ports)[:50])

        hosts = hosts_by_port[flow.port]
        if len(hosts) >= HOST_SWEEP_THRESHOLD and self._cooled_down(("host_sweep", flow.mac, flow.port)):
            self.emit("alert", "medium",
                      f"{name} contacted {len(hosts)} devices on port {flow.port} in under a minute",
                      mac=flow.mac, rule="host_sweep", port=flow.port, hosts=len(hosts))

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _days_away(previous_last_seen: str | None) -> int:
        if not previous_last_seen:
            return 0
        return (utcnow() - parse_iso(previous_last_seen)).days

    def _check_conflict(self, mac: str, ip: str, previous_mac: str, name: str) -> None:
        if mac == self.own_mac:
            return  # this computer changing address is not an attack; others claiming its IP still is
        previous = self.store.get(previous_mac)
        previous_name = label(previous, previous_mac)

        if ip == self.gateway_ip:
            if self._cooled_down(("gateway_conflict", mac)):
                self.emit("mac_conflict", "critical",
                          f"Router address {ip} is now claimed by {name} (was {previous_name}). "
                          "This can mean another device is intercepting your traffic.",
                          mac=mac, ip=ip, previous_mac=previous_mac)
            return

        recently_active = previous and utcnow() - parse_iso(previous.last_seen) < timedelta(seconds=CONFLICT_ACTIVE_S)
        if recently_active and self._cooled_down(("mac_conflict", mac, ip)):
            self.emit("mac_conflict", "high",
                      f"{name} and {previous_name} are both using {ip}",
                      mac=mac, ip=ip, previous_mac=previous_mac)
