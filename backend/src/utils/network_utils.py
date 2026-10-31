import psutil
import socket

def get_active_interfaces():
    interfaces = []
    for iface_name, iface_info in psutil.net_if_stats().items():
        if iface_info.isup and not iface_name.lower().startswith("lo"):
            interfaces.append(iface_name)
    return sorted(interfaces)

def get_gateway_ips() -> set:
    """Return a best-guess set of gateway IPs for the active network."""
    gateways = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
        prefix = local_ip.rsplit(".", 1)[0]
        gateways.add(f"{prefix}.1")
    except Exception:
        pass
    return gateways

def get_interface_ip(iface_name):
    addrs = psutil.net_if_addrs().get(iface_name, [])
    for addr in addrs:
        if addr.family == socket.AF_INET:
            return addr.address
    return "N/A"
