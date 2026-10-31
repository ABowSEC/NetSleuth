"""Pick which network interface to watch."""
from __future__ import annotations

import ipaddress
import socket

import psutil


def candidate_interfaces() -> list[tuple[str, str]]:
    """(name, IPv4) for every interface that is up and has a usable IPv4 address."""
    stats = psutil.net_if_stats()
    result = []
    for name, addrs in psutil.net_if_addrs().items():
        if not stats.get(name) or not stats[name].isup:
            continue
        for addr in addrs:
            if addr.family != socket.AF_INET:
                continue
            ip = ipaddress.IPv4Address(addr.address)
            if ip.is_loopback or ip.is_link_local:
                continue
            result.append((name, addr.address))
            break
    return sorted(result)


def internet_facing_ip() -> str | None:
    """The local IP the OS would use to reach the internet. Sends no packets."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # TEST-NET-1: never routed, only used to pick a route
            return s.getsockname()[0]
    except OSError:
        return None


def default_interface(candidates: list[tuple[str, str]], route_ip: str | None) -> str | None:
    """The interface carrying the default route, else the only/first candidate."""
    for name, ip in candidates:
        if ip == route_ip:
            return name
    return candidates[0][0] if candidates else None
