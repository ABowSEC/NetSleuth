# analyzer.py
from scapy.layers.inet import TCP, UDP, IP
from scapy.layers.dns  import DNS
from scapy.layers.l2   import ARP, Ether
from scapy.packet      import Raw
import time
from .device_tracker import update_device   #  (ip, mac, field, value)

VERBOSE = False  # True = per-packet prints
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
        # Fallback extraction if sniffer didn’t supply values
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

        # UDP (non-DNS)
        if pkt.haslayer(UDP) and not pkt.haslayer(DNS):
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
    qname = pkt[DNS].qd.qname.decode(errors="ignore").rstrip('.')
    update_device(ip_src, mac_src, "dns_queries", qname)

def handle_udp(udp, ip_src, ip_dst, mac_src, now):
    if not ip_src or not ip_dst:
        return
    if VERBOSE:
        print(colored(f"[{now}] [UDP] {ip_src}:{udp.sport} → {ip_dst}:{udp.dport}", "blue"))
    update_device(ip_src, mac_src, "connections", f"{ip_dst}:{udp.dport}")

def handle_tcp(tcp, ip_src, ip_dst, mac_src, now):
    if not ip_src or not ip_dst:
        return
    flags = tcp.sprintf("%TCP.flags%")
    if VERBOSE:
        print(colored(f"[{now}] [TCP] {ip_src}:{tcp.sport} → {ip_dst}:{tcp.dport} [{flags}]", "cyan"))
    update_device(ip_src, mac_src, "connections", f"{ip_dst}:{tcp.dport}")
