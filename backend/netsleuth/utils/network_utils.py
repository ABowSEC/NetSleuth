import ipaddress
import socket
from dataclasses import dataclass

import psutil


def get_active_interfaces():
    interfaces = []
    for iface_name, iface_info in psutil.net_if_stats().items():
        if iface_info.isup and not iface_name.lower().startswith("lo"):
            interfaces.append(iface_name)
    return sorted(interfaces)


@dataclass(frozen=True)
class InterfaceInfo:
    name: str
    ip: str
    network: ipaddress.IPv4Network


def interface_info(name: str) -> InterfaceInfo | None:
    """IPv4 address and subnet of ``name`` (from its real netmask), or None."""
    for addr in psutil.net_if_addrs().get(name, []):
        if addr.family == socket.AF_INET and addr.netmask:
            iface = ipaddress.IPv4Interface(f"{addr.address}/{addr.netmask}")
            return InterfaceInfo(name, addr.address, iface.network)
    return None


def default_gateway_ip() -> str | None:
    """IPv4 default gateway from the OS routing table, via scapy."""
    try:
        from scapy.config import conf
        gateway = conf.route.route("0.0.0.0")[2]
    except Exception:
        return None
    return gateway if gateway and gateway != "0.0.0.0" else None


def get_gateway_ips() -> set:
    """Return a best-guess set of gateway IPs for the active network."""
    gateway = default_gateway_ip()
    return {gateway} if gateway else set()
