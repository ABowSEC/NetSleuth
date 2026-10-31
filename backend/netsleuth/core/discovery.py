"""Active discovery: periodic ARP sweep of the local subnet.

Passive capture only sees devices that talk. A sweep finds quiet ones
(printers, idle phones) and keeps presence accurate.
"""
from __future__ import annotations

import logging
import threading
from ipaddress import IPv4Network, ip_network
from typing import Callable, Iterable

from .packets import Sighting
from .pipeline import Pipeline
from ..utils.mac import normalize_mac

log = logging.getLogger(__name__)

MAX_PREFIX = 22          # never sweep more than a /22 (1022 hosts)
FIRST_SWEEP_DELAY_S = 5


def sweep_target(network: IPv4Network, own_ip: str) -> IPv4Network:
    """The subnet to sweep: ``network``, narrowed to a /22 around us if larger."""
    if network.prefixlen >= MAX_PREFIX:
        return network
    narrowed = ip_network(f"{own_ip}/{MAX_PREFIX}", strict=False)
    log.warning("Subnet %s is large; sweeping only %s", network, narrowed)
    return narrowed


def arp_sweep(iface: str, target: IPv4Network, timeout: float = 2.0) -> list[tuple[str, str]]:
    """Broadcast ARP who-has for every host in ``target``; return (mac, ip) replies."""
    from scapy.layers.l2 import ARP, Ether
    from scapy.sendrecv import srp

    answered, _ = srp(
        Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=str(target)),
        iface=iface, timeout=timeout, verbose=False,
    )
    return [(reply[ARP].hwsrc, reply[ARP].psrc) for _, reply in answered]


class Discovery:
    def __init__(
        self,
        pipeline: Pipeline,
        iface: str,
        own_ip: str,
        interval_s: Callable[[], int],
        sweeper: Callable[[str, IPv4Network], Iterable[tuple[str, str]]] = arp_sweep,
    ):
        self._pipeline = pipeline
        self._iface = iface
        self._target = sweep_target(pipeline.network, own_ip)
        self._interval_s = interval_s
        self._sweeper = sweeper
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def sweep_once(self) -> int:
        """Run one sweep (unless paused). Returns the number of replies."""
        if self._pipeline.paused:
            return 0
        facts = []
        for raw_mac, ip in self._sweeper(self._iface, self._target):
            mac = normalize_mac(raw_mac)
            if mac:
                facts.append(Sighting(mac, ip))
        self._pipeline.apply(facts)
        log.debug("ARP sweep of %s: %d device(s) answered", self._target, len(facts))
        return len(facts)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="discovery", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        delay = FIRST_SWEEP_DELAY_S
        while not self._stop.wait(delay):
            try:
                self.sweep_once()
            except Exception:
                log.exception("ARP sweep failed")
            delay = self._interval_s()
