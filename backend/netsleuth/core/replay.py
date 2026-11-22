"""Replay a capture file through the pipeline in place of live capture.

Replay mode sends nothing: there is no ARP sweep and no Identify probing. It
exists so NetSleuth can be developed, tested and demonstrated without a live
network (see docs/ROADMAP.md).

Time: the pipeline's UDP de-duplication and the event engine's alert windows
run on the capture's own timestamps (``ReplayClock``), so a fast replay raises
the same alerts as the original traffic. Stored timestamps (first/last seen,
events) are still wall-clock times.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from ipaddress import IPv4Address, IPv4Network, ip_network
from pathlib import Path
from typing import Callable

from .pipeline import HOUSEKEEPING_S, Pipeline

log = logging.getLogger(__name__)

INFER_SAMPLE = 2000


class ReplayError(RuntimeError):
    """The capture file can't be read."""


class ReplayClock:
    """A monotonic-style clock that follows the replayed packets' timestamps."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, ts: float) -> None:
        if ts > self.now:          # capture files can be slightly out of order
            self.now = ts


def _reader(path: Path):
    from scapy.error import Scapy_Exception
    from scapy.utils import PcapReader

    if not path.is_file():
        raise ReplayError(f"Capture file not found: {path}")
    try:
        return PcapReader(str(path))
    except (OSError, Scapy_Exception) as e:
        raise ReplayError(f"Can't read {path}: {e}") from e


def first_timestamp(path: Path) -> float | None:
    with _reader(path) as reader:
        for pkt in reader:
            return float(pkt.time)
    return None


def infer_network(path: Path, sample: int = INFER_SAMPLE) -> IPv4Network | None:
    """Guess the LAN: the /24 holding the most common private source address."""
    from scapy.layers.inet import IP
    from scapy.layers.l2 import ARP

    counts: Counter[str] = Counter()
    with _reader(path) as reader:
        for i, pkt in enumerate(reader):
            if i >= sample:
                break
            if IP in pkt:
                src = pkt[IP].src
            elif ARP in pkt:
                src = pkt[ARP].psrc
            else:
                continue
            try:
                addr = IPv4Address(src)
            except ValueError:
                continue
            if addr.is_private and not addr.is_loopback and not addr.is_link_local and src != "0.0.0.0":
                counts[str(ip_network(f"{src}/24", strict=False))] += 1
    if not counts:
        return None
    return ip_network(counts.most_common(1)[0][0])


def replay(
    path: Path,
    pipeline: Pipeline,
    clock: ReplayClock | None = None,
    speed: float = 0.0,
    max_gap_s: float = 5.0,
    stop: threading.Event | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Feed every packet in ``path`` through ``pipeline``. Returns packets processed.

    ``speed`` 0 replays as fast as possible; 1 keeps the original pacing, 10 is
    ten times faster. Gaps longer than ``max_gap_s`` (in capture time) are cut
    short so an idle stretch doesn't stall a demo. Packets arriving while
    monitoring is paused are skipped, as they would be live.
    """
    processed = 0
    previous: float | None = None
    last_tick: float | None = None
    with _reader(path) as reader:
        for pkt in reader:
            if stop is not None and stop.is_set():
                break
            ts = float(pkt.time)
            # Time-based event rules (the first-run summary) tick on capture time too.
            if last_tick is None:
                last_tick = ts
            elif ts - last_tick >= HOUSEKEEPING_S:
                pipeline.observer.on_tick()
                last_tick = ts
            if speed > 0 and previous is not None:
                gap = min(max(ts - previous, 0.0), max_gap_s) / speed
                if gap > 0:
                    sleep(gap)
            previous = ts
            if clock is not None:
                clock.advance(ts)
            if pipeline.paused:
                continue
            try:
                pipeline.process(pkt, now=ts)
            except Exception:
                log.exception("Failed to process replayed packet")
            processed += 1
    if processed:
        pipeline.observer.on_tick()
    log.info("Replayed %d packet(s) from %s", processed, path)
    return processed
