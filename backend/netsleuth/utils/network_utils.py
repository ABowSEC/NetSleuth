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
    mac: str | None = None


def interface_info(name: str) -> InterfaceInfo | None:
    """IPv4 address, subnet (from its real netmask) and MAC of ``name``, or None."""
    from .mac import normalize_mac

    addrs = psutil.net_if_addrs().get(name, [])
    mac = next((normalize_mac(a.address) for a in addrs if a.family == psutil.AF_LINK), None)
    for addr in addrs:
        if addr.family == socket.AF_INET and addr.netmask:
            iface = ipaddress.IPv4Interface(f"{addr.address}/{addr.netmask}")
            return InterfaceInfo(name, addr.address, iface.network, mac)
    return None


def default_gateway_ip() -> str | None:
    """IPv4 default gateway from the OS routing table, via scapy."""
    try:
        from scapy.config import conf
        gateway = conf.route.route("0.0.0.0")[2]
    except Exception:
        return None
    return gateway if gateway and gateway != "0.0.0.0" else None

