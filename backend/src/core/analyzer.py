# analyzer.py
from scapy.layers.inet import TCP, UDP, IP
from scapy.layers.dns  import DNS
from scapy.layers.l2   import ARP, Ether
from scapy.packet      import Raw
try:
    from scapy.layers.dhcp import DHCP, BOOTP
    _DHCP_AVAILABLE = True
except ImportError:
    _DHCP_AVAILABLE = False
import time
import logging
import ipaddress
from .device_tracker import update_device

_PRIVATE_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    ipaddress.ip_network('169.254.0.0/16'),
]

def _is_local(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False

try:
    from config import VERBOSE, DEBUG_MODE
except ImportError:
    VERBOSE = False
    DEBUG_MODE = False

logger = logging.getLogger(__name__)

devices_seen = {}

_COLORS = {
    "magenta": "\033[95m", "blue": "\033[94m", "green": "\033[92m",
    "yellow": "\033[93m", "red": "\033[91m", "cyan": "\033[96m",
    "reset":  "\033[0m"
}
def colored(text, color):
    return f"{_COLORS[color]}{text}{_COLORS['reset']}"

#Main Dispatch
def analyze_packet(pkt, mac_src=None, ip_src=None, ip_dst=None):
    """Parse one Scapy packet; update device log."""
    now = time.strftime('%H:%M:%S')

    try:
        # Fallback extraction if sniffer didn't supply values
        if mac_src is None and pkt.haslayer(Ether):
            mac_src = pkt[Ether].src.lower()
        if ip_src is None and pkt.haslayer(IP):
            ip_src = pkt[IP].src
        if ip_dst is None and pkt.haslayer(IP):
            ip_dst = pkt[IP].dst

        # ARP
        if pkt.haslayer(ARP):
            handle_arp(pkt[ARP], mac_src, now)

        # DNS (UDP/53)
        if pkt.haslayer(DNS):
            handle_dns(pkt, mac_src, ip_src, now)

        # DHCP: must be checked before generic UDP so port 67/68 isn't logged as a connection
        if _DHCP_AVAILABLE and pkt.haslayer(DHCP):
            handle_dhcp(pkt, now)

        # UDP (non-DNS, non-DHCP)
        elif pkt.haslayer(UDP) and not pkt.haslayer(DNS):
            handle_udp(pkt[UDP], ip_src, ip_dst, mac_src, now)

        # TCP
        if pkt.haslayer(TCP):
            handle_tcp(pkt[TCP], ip_src, ip_dst, mac_src, now)

        # Optional mDNS / service discovery inspection
        if pkt.haslayer(Raw):
            raw = bytes(pkt[Raw])
            if b'model=' in raw or b'manufacturer=' in raw:
                if VERBOSE:
                    print(colored(f"[{now}] [mDNS] Possible device info: {raw}", "green"))

    except Exception as e:
        logger.debug("Error processing packet: %s", e, exc_info=True)
        if VERBOSE:
            print(colored(f"[!] Error processing packet: {e}", "red"))

# Layer-specific handlers

def handle_arp(arp, mac_src, now):
    if VERBOSE:
        print(colored(f"[{now}] [ARP] {arp.psrc} → {arp.pdst}", "yellow"))
    update_device(arp.psrc, mac_src, "services", f"ARP→{arp.pdst}")

def handle_dns(pkt, mac_src, ip_src, now):
    if not ip_src:
        return
    if VERBOSE:
        print(colored(f"[{now}] [DNS] Query from {ip_src}", "magenta"))
    
    # Safely extract DNS query name
    try:
        if pkt[DNS].qd and pkt[DNS].qd.qname:
            qname = pkt[DNS].qd.qname.decode(errors="ignore").rstrip('.')
            update_device(ip_src, mac_src, "dns_queries", qname)
    except (AttributeError, IndexError):
        # DNS packet doesn't have expected structure
        pass

def handle_udp(udp, ip_src, ip_dst, mac_src, now):
    if not ip_src or not ip_dst or not _is_local(ip_src):
        return
    if VERBOSE:
        print(colored(f"[{now}] [UDP] {ip_src}:{udp.sport} -> {ip_dst}:{udp.dport}", "blue"))
    update_device(ip_src, mac_src, "connections", f"{ip_dst}:{udp.dport}")

def handle_dhcp(pkt, now):
    try:
        chaddr = pkt[BOOTP].chaddr
        mac = ':'.join(f'{b:02x}' for b in chaddr[:6])

        options = {}
        for opt in pkt[DHCP].options:
            if isinstance(opt, tuple) and len(opt) == 2:
                options[opt[0]] = opt[1]

        ip = pkt[BOOTP].ciaddr
        if ip == '0.0.0.0':
            ip = options.get('requested_addr')
        if not ip or ip == '0.0.0.0':
            return

        hostname = options.get('hostname', b'')
        if isinstance(hostname, bytes):
            hostname = hostname.decode('utf-8', errors='ignore').strip()

        if hostname:
            update_device(ip, mac, 'hostname', hostname)
            if VERBOSE:
                print(colored(f"[{now}] [DHCP] {ip} ({mac}) -> {hostname}", "green"))
    except Exception as e:
        logger.debug("DHCP parse error: %s", e)

def handle_tcp(tcp, ip_src, ip_dst, mac_src, now):
    if not ip_src or not ip_dst or not _is_local(ip_src):
        return
    flags = tcp.sprintf("%TCP.flags%")
    if VERBOSE:
        print(colored(f"[{now}] [TCP] {ip_src}:{tcp.sport} -> {ip_dst}:{tcp.dport} [{flags}]", "cyan"))
    update_device(ip_src, mac_src, "connections", f"{ip_dst}:{tcp.dport}")
