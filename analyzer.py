from scapy.layers.inet import TCP, UDP, IP
from scapy.layers.dns import DNS
from scapy.layers.l2 import ARP
from scapy.packet import Raw
import time
from deviceTracker import update_device

VERBOSE = False  # Set to True to enable per-packet prints

# ANSI color scheme
def colored(text, color):
    colors = {
        "magenta": "\033[95m",
        "blue": "\033[94m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "red": "\033[91m",
        "cyan": "\033[96m",
        "reset": "\033[0m"
    }
    return f"{colors[color]}{text}{colors['reset']}"

devices_seen = {}

def analyze_packet(packet):
    now = time.strftime('%H:%M:%S')

    handlers = {
        'ARP': lambda pkt: handle_arp(pkt, now),
        'DNS': lambda pkt: handle_dns(pkt, now),
        'UDP': lambda pkt: handle_udp(pkt, now),
        'TCP': lambda pkt: handle_tcp(pkt, now)
    }

    for layer_name, handler in handlers.items():
        if packet.haslayer(eval(layer_name)):
            handler(packet)

    if packet.haslayer(Raw):
        raw_data = bytes(packet[Raw])
        if b'model=' in raw_data or b'manufacturer=' in raw_data:
            if VERBOSE:
                print(colored(f"[{now}] [mDNS] Possible device info: {raw_data}", "green"))

def handle_arp(packet, now):
    arp = packet[ARP]
    if VERBOSE:
        print(colored(f"[{now}] [ARP] {arp.psrc} is asking about {arp.pdst}", "yellow"))
    devices_seen[arp.psrc] = {'type': 'ARP', 'last_seen': now}
    update_device(arp.psrc, "connections", f"ARP→{arp.pdst}")

def handle_dns(packet, now):
    if VERBOSE:
        print(colored(f"[{now}] [DNS] Query Detected", "magenta"))
    if packet.haslayer(IP):
        src_ip = packet[IP].src
        if VERBOSE:
            print(colored(f"[{now}] [DNS] From {src_ip}", "magenta"))
        devices_seen[src_ip] = {'type': 'DNS', 'last_seen': now}
        if packet.haslayer(Raw):
            raw_data = bytes(packet[Raw])
            if b"." in raw_data:
                try:
                    domain = raw_data.split(b"\x00")[0].decode(errors="ignore")
                    update_device(src_ip, "dns_queries", domain)
                except:
                    pass

def handle_udp(packet, now):
    udp = packet[UDP]
    src = packet[IP].src if packet.haslayer(IP) else "?"
    dst = packet[IP].dst if packet.haslayer(IP) else "?"
    if VERBOSE:
        print(colored(f"[{now}] [UDP] {src}:{udp.sport} → {dst}:{udp.dport}", "blue"))
    devices_seen[src] = {'type': 'UDP', 'last_seen': now}
    update_device(src, "connections", f"{dst}:{udp.dport}")

def handle_tcp(packet, now):
    tcp = packet[TCP]
    src = packet[IP].src if packet.haslayer(IP) else "?"
    dst = packet[IP].dst if packet.haslayer(IP) else "?"
    flags = tcp.sprintf("%TCP.flags%")
    if VERBOSE:
        print(colored(f"[{now}] [TCP] {src}:{tcp.sport} → {dst}:{tcp.dport} [{flags}]", "cyan"))
    devices_seen[src] = {'type': 'TCP', 'last_seen': now}
    update_device(src, "connections", f"{dst}:{tcp.dport}")
