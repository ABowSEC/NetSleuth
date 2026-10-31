"""Packet pipeline: capture thread -> queue -> worker -> store.

The capture callback (``submit``) only enqueues. Parsing, store updates and
observer callbacks all run on the worker thread, so a slow or failing step
never stalls or kills capture.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from ipaddress import IPv4Network
from typing import Callable

from .packets import Clue, Fact, Flow, Hostname, Query, Sighting, parse
from .store import Device, DeviceStore, Observation

log = logging.getLogger(__name__)

QUEUE_SIZE = 10_000
UDP_FLOW_WINDOW_S = 60      # one UDP "flow" per (mac, dst, port) per window
HOUSEKEEPING_S = 30
PRUNE_EVERY_S = 3600


class PipelineObserver:
    """Hooks for the event/alert layer. Default implementation does nothing."""

    def on_sighting(self, mac: str, ip: str | None, obs: Observation) -> None: ...

    def on_offline(self, devices: list[Device]) -> None: ...

    def on_tick(self) -> None:
        """Called on every housekeeping pass (~30 s)."""

    def on_flow(self, flow: Flow) -> None: ...


class Pipeline:
    def __init__(
        self,
        store: DeviceStore,
        network: IPv4Network,
        gateway_ip: str | None = None,
        observer: PipelineObserver | None = None,
        offline_timeout_s: Callable[[], int] = lambda: 600,
        retention_days: Callable[[], int] = lambda: 30,
    ):
        self.store = store
        self.network = network
        self.gateway_ip = gateway_ip
        self.observer = observer or PipelineObserver()
        self._offline_timeout_s = offline_timeout_s
        self._retention_days = retention_days

        self._queue: queue.Queue = queue.Queue(maxsize=QUEUE_SIZE)
        self._stop = threading.Event()
        self._paused = threading.Event()
        self._threads: list[threading.Thread] = []
        self._recent_udp: dict[tuple[str, str, int | None], float] = {}
        self.dropped = 0

    # ── Control ──────────────────────────────────────────────────────────────

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def pause(self) -> None:
        self._paused.set()

    def resume(self) -> None:
        self._paused.clear()

    def start(self) -> None:
        for target, name in ((self._work, "pipeline-worker"), (self._housekeep, "pipeline-housekeeping")):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)

    def stop(self) -> None:
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=5)
        self._threads.clear()

    # ── Capture side ─────────────────────────────────────────────────────────

    def submit(self, pkt) -> None:
        """Scapy ``prn`` callback. Must never raise or block."""
        if self._paused.is_set():
            return
        try:
            self._queue.put_nowait(pkt)
        except queue.Full:
            self.dropped += 1
            if self.dropped % 1000 == 1:
                log.warning("Packet queue full; dropped %d packet(s) so far", self.dropped)

    # ── Worker side ──────────────────────────────────────────────────────────

    def _work(self) -> None:
        while not self._stop.is_set():
            try:
                pkt = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self.apply(parse(pkt, self.network))
            except Exception:
                log.exception("Failed to process packet")

    def apply(self, facts: list[Fact], now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        for fact in facts:
            if isinstance(fact, Sighting):
                obs = self.store.observe(fact.mac, fact.ip)
                if fact.ip and fact.ip == self.gateway_ip:
                    self.store.mark_gateway(fact.mac)
                self.observer.on_sighting(fact.mac, fact.ip, obs)
            elif isinstance(fact, Hostname):
                self.store.set_hostname(fact.mac, fact.hostname)
            elif isinstance(fact, Query):
                self.store.record_domain(fact.mac, fact.domain)
            elif isinstance(fact, Clue):
                self.store.add_evidence(fact.mac, fact.source, fact.key, fact.value, fact.confidence)
            elif isinstance(fact, Flow):
                if fact.proto == "udp" and not self._new_udp_flow(fact, now):
                    continue
                self.store.record_destination(fact.mac, fact.address, fact.port)
                self.observer.on_flow(fact)

    def _new_udp_flow(self, flow: Flow, now: float) -> bool:
        key = (flow.mac, flow.address, flow.port)
        last = self._recent_udp.get(key)
        if last is not None and now - last < UDP_FLOW_WINDOW_S:
            return False
        self._recent_udp[key] = now
        if len(self._recent_udp) > 50_000:
            cutoff = now - UDP_FLOW_WINDOW_S
            self._recent_udp = {k: t for k, t in self._recent_udp.items() if t >= cutoff}
        return True

    # ── Housekeeping ─────────────────────────────────────────────────────────

    def housekeeping(self) -> None:
        gone = self.store.expire(self._offline_timeout_s())
        if gone:
            self.observer.on_offline(gone)
        self.observer.on_tick()

    def _housekeep(self) -> None:
        last_prune = time.monotonic()
        while not self._stop.wait(HOUSEKEEPING_S):
            try:
                self.housekeeping()
                if time.monotonic() - last_prune >= PRUNE_EVERY_S:
                    self.store.prune(self._retention_days())
                    last_prune = time.monotonic()
            except Exception:
                log.exception("Housekeeping failed")
