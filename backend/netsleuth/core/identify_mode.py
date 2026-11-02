"""Identify mode: a time-boxed pass of active probes that switches itself off.

Nothing here runs unless a user starts it. A run:
1. sends one SSDP search and one mDNS service query for the whole network;
2. probes each target device (UPnP description, NetBIOS name, reverse DNS,
   and the port check only if the user enabled it), at most ``workers``
   hosts at a time and at least ``spacing`` seconds between host starts;
3. records what it learns as evidence, then emits one ``identified`` event.

It stops early (and says why) when the deadline passes, monitoring is
paused, or ``stop()`` is called.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import timedelta
from ipaddress import IPv4Network
from typing import Callable

from ..timeutil import iso, parse_iso, utcnow
from . import probes
from .events import EventEngine
from .store import Device, DeviceStore

log = logging.getLogger(__name__)

RECENTLY_IDENTIFIED = timedelta(hours=1)  # only guards against a double click; a user asking means run
HTTP_TITLE_PORTS = (80, 8080, 8060)


class AlreadyRunning(Exception):
    pass


class MonitoringPaused(Exception):
    pass


@dataclass
class Probers:
    """The network calls a run makes. Swapped for fakes in tests."""
    ssdp_search: Callable[[str], dict[str, dict[str, str]]] = probes.ssdp_search
    fetch_description: Callable[[str, IPv4Network], dict[str, str]] = probes.fetch_description
    mdns_query: Callable[[str], int] = probes.mdns_query
    netbios_name: Callable[[str], str | None] = probes.netbios_name
    reverse_dns: Callable[[str], str | None] = probes.reverse_dns
    port_check: Callable[[str], list[int]] = probes.port_check
    http_title: Callable[[str, int], str | None] = probes.http_title


def _identity(device: Device | None) -> tuple:
    return (device.type, device.model, device.os, device.suggested_name) if device else ()


class IdentifySession:
    def __init__(
        self,
        store: DeviceStore,
        engine: EventEngine,
        network: IPv4Network,
        own_ip: str,
        own_mac: str | None = None,
        gateway_ip: str | None = None,
        port_check_enabled: Callable[[], bool] = lambda: False,
        is_paused: Callable[[], bool] = lambda: False,
        probers: Probers | None = None,
        clock: Callable[[], float] = time.monotonic,
        workers: int = 4,
        spacing: float = 0.2,
    ):
        self.store = store
        self.engine = engine
        self.network = network
        self.own_ip = own_ip
        self.own_mac = own_mac
        self.gateway_ip = gateway_ip
        self._port_check_enabled = port_check_enabled
        self._is_paused = is_paused
        self.probers = probers or Probers()
        self._clock = clock
        self._workers = workers
        self._spacing = spacing

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._subscribers: list[Callable[[dict], None]] = []
        self._status = self._idle_status()

    # ── Status ───────────────────────────────────────────────────────────────

    @staticmethod
    def _idle_status() -> dict:
        return {"running": False, "started_at": None, "ends_at": None, "done": 0, "total": 0,
                "current": None, "port_check": False}

    def status(self) -> dict:
        with self._lock:
            return dict(self._status)

    def subscribe(self, fn: Callable[[dict], None]) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(fn)

        def unsubscribe() -> None:
            with self._lock:
                if fn in self._subscribers:
                    self._subscribers.remove(fn)
        return unsubscribe

    def _update(self, **changes) -> None:
        with self._lock:
            self._status.update(changes)
            snapshot, subscribers = dict(self._status), list(self._subscribers)
        for fn in subscribers:
            try:
                fn(snapshot)
            except Exception:
                log.exception("Identify status subscriber failed")

    # ── Control ──────────────────────────────────────────────────────────────

    def targets(self, macs: list[str] | None = None) -> list[tuple[str, str]]:
        """(mac, ip) for online devices to probe; recently identified ones are skipped unless named."""
        now = utcnow()
        wanted = set(macs) if macs else None
        result = []
        for device in self.store.list_devices(status="online"):
            if device.mac == self.own_mac or not device.ips:
                continue
            if wanted is not None:
                if device.mac not in wanted:
                    continue
            elif device.last_identified and now - parse_iso(device.last_identified) < RECENTLY_IDENTIFIED:
                continue
            result.append((device.mac, device.ips[0]))
        return result

    def start(self, minutes: int, macs: list[str] | None = None) -> dict:
        if self._is_paused():
            raise MonitoringPaused()
        with self._lock:
            if self._status["running"]:
                raise AlreadyRunning()
            self._stop.clear()
            targets = self.targets(macs)
            started = utcnow()
            self._deadline = self._clock() + minutes * 60
            self._status = {
                "running": True, "started_at": iso(started), "ends_at": iso(started + timedelta(minutes=minutes)),
                "done": 0, "total": len(targets), "current": "Starting", "port_check": self._port_check_enabled(),
            }
            self._thread = threading.Thread(target=self._run, args=(targets,), name="identify", daemon=True)
            self._thread.start()
        self._update()
        return self.status()

    def stop(self, wait: float = 10.0) -> dict:
        self._stop.set()
        if self._thread:
            self._thread.join(wait)
        return self.status()

    def _halt_reason(self) -> str | None:
        if self._stop.is_set():
            return "stopped"
        if self._is_paused():
            return "paused"
        if self._clock() >= self._deadline:
            return "time limit"
        return None

    # ── Run ──────────────────────────────────────────────────────────────────

    def _run(self, targets: list[tuple[str, str]]) -> None:
        before = {mac: _identity(self.store.get(mac)) for mac, _ in targets}
        port_check = self._status["port_check"]
        reason = None
        try:
            self._update(current="Asking devices to describe themselves")
            ssdp = self._safely(self.probers.ssdp_search, self.own_ip) or {}
            self._safely(self.probers.mdns_query, self.own_ip)

            with ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="identify-host") as pool:
                futures = []
                for mac, ip in targets:
                    reason = self._halt_reason()
                    if reason:
                        break
                    futures.append(pool.submit(self._probe_host, mac, ip, ssdp.get(ip, {}), port_check))
                    if self._stop.wait(self._spacing):
                        reason = "stopped"
                        break
                for future in futures:
                    future.result()
            reason = reason or self._halt_reason()
        except Exception:
            log.exception("Identify run failed")
            reason = "error"
        finally:
            self._finish(targets, before, reason)

    def _probe_host(self, mac: str, ip: str, ssdp_headers: dict[str, str], port_check: bool) -> None:
        if self._halt_reason():
            return
        self._update(current=ip)
        add = lambda source, key, value, confidence=1.0: value and self.store.add_evidence(  # noqa: E731
            mac, source, key, str(value), confidence)

        found: dict[str, object] = {}
        if ssdp_headers.get("server"):
            add("ssdp", "server", ssdp_headers["server"], 0.6)
        # Some devices only announce themselves (NOTIFY) and never answer a search:
        # fall back to the description URL the passive listener already recorded.
        stored = {(e.source, e.key): e.value for e in self.store.evidence(mac)}
        location = ssdp_headers.get("location") or stored.get(("ssdp", "location"))
        if location:
            add("ssdp", "location", location, 0.5)
            description = self._safely(self.probers.fetch_description, location, self.network) or {}
            for key, value in description.items():
                add("upnp", key, value)
            found["upnp"] = description.get("modelName") or description.get("friendlyName") or bool(description)
        found["netbios"] = self._safely(self.probers.netbios_name, ip)
        found["rdns"] = self._safely(self.probers.reverse_dns, ip)
        add("netbios", "name", found["netbios"], 0.9)
        add("rdns", "name", found["rdns"], 0.6)

        if port_check and ip != self.gateway_ip:
            open_ports = self._safely(self.probers.port_check, ip) or []
            found["ports"] = ",".join(map(str, open_ports)) or None
            if open_ports:
                add("ports", "open", ",".join(map(str, sorted(open_ports))), 0.8)
                for port in HTTP_TITLE_PORTS:
                    if port in open_ports:
                        add("ports", "http_title", self._safely(self.probers.http_title, ip, port), 0.5)
                        break

        # One line per device, so a quiet run can be diagnosed from the log.
        log.info("Identify %s: %s", ip, ", ".join(f"{k}={v or '-'}" for k, v in found.items()))
        self.store.mark_identified(mac)
        with self._lock:
            self._status["done"] += 1
        self._update()

    @staticmethod
    def _safely(fn, *args):
        try:
            return fn(*args)
        except Exception:
            log.debug("Probe %s%s failed", getattr(fn, "__name__", fn), args, exc_info=True)
            return None

    def _finish(self, targets: list[tuple[str, str]], before: dict, reason: str | None) -> None:
        improved = []
        for mac, _ in targets:
            device = self.store.get(mac)
            if device and _identity(device) != before.get(mac):
                improved.append(device)
        examples = [d.model or d.suggested_name for d in improved if d.model or d.suggested_name][:3]
        done = self.status()["done"]

        if not targets:
            message = "Identify found nothing to check: every online device was checked in the last hour."
        else:
            message = f"Identify finished: learned more about {len(improved)} of {len(targets)} devices"
            message += f" ({', '.join(examples)}{', …' if len(improved) > len(examples) else ''})." if examples else "."
            if reason in ("stopped", "paused", "time limit", "error"):
                why = {"stopped": "it was stopped", "paused": "monitoring was paused",
                       "time limit": "it reached its time limit", "error": "of an error (see the log)"}[reason]
                message += f" It checked {done} of {len(targets)} before ending because {why}."
        self.engine.emit("identified", "info", message,
                         total=len(targets), checked=done, improved=[d.mac for d in improved], reason=reason)
        self._update(**self._idle_status())
