"""Blocking layer-2 packet capture.

Device identity is the MAC address, so capture must be layer 2. There is no
IP-only fallback: without Ethernet headers nothing can be attributed.
"""
from __future__ import annotations

import sys
from typing import Callable

_PERMISSION_HINTS = ("permission", "access is denied", "denied", "operation not permitted")


class CaptureError(RuntimeError):
    """Capture cannot start (e.g. Npcap/libpcap missing)."""


class CapturePermissionError(CaptureError):
    """The OS refused raw capture for this user."""


def run_capture(iface: str, on_packet: Callable) -> None:
    """Capture on ``iface`` until interrupted, passing each packet to ``on_packet``."""
    from scapy.config import conf
    from scapy.error import Scapy_Exception
    from scapy.sendrecv import sniff

    if sys.platform == "win32" and not conf.use_pcap:
        raise CaptureError("Npcap is not installed. Get it from https://npcap.com and restart NetSleuth.")

    try:
        sniff(iface=iface, prn=on_packet, store=False)
    except PermissionError as e:
        raise CapturePermissionError(str(e)) from e
    except (OSError, Scapy_Exception) as e:
        if any(hint in str(e).lower() for hint in _PERMISSION_HINTS):
            raise CapturePermissionError(str(e)) from e
        raise CaptureError(str(e)) from e
