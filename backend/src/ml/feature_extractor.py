# feature_extractor.py
import time
from collections import OrderedDict
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.packet import Packet

try:
    from config import ML_LAST_SEEN_MAX
except ImportError:
    ML_LAST_SEEN_MAX = 2000

# Bounded OrderedDict: evicts oldest entry when cap is reached
_last_seen: OrderedDict = OrderedDict()

FEATURE_NAMES = [
    "packet_size",
    "ip_total_length",
    "protocol",
    "src_port",
    "dst_port",
    "tcp_flags",
    "ttl",
    "entropy_like",
    "inter_arrival",
    "is_broadcast"
]

def extract_features(pkt: Packet):
    """
    Extract lightweight, ML-friendly numeric features.
    Compatible with IsolationForest without normalization.

    """

    # Drop packets without IP - ARP |-| LLDP still handled elsewhere
    if not pkt.haslayer(IP):
        return None

    ip = pkt[IP]

    #  basic 
    size = len(pkt)
    ip_len = ip.len
    ttl = ip.ttl

    #  protocol encoding 
    protocol = 0
    src_port = 0
    dst_port = 0
    tcp_flags = 0

    if pkt.haslayer(TCP):
        protocol = 1
        src_port = pkt[TCP].sport
        dst_port = pkt[TCP].dport
        tcp_flags = int(pkt[TCP].flags)

    elif pkt.haslayer(UDP):
        protocol = 2
        src_port = pkt[UDP].sport
        dst_port = pkt[UDP].dport

    elif pkt.haslayer(ICMP):
        protocol = 3

    #  entropy-like heuristic 
    # For anomalies: high entropy = encrypted/random payload
    # Normal: mDNS/SSDP have patterned payloads (low)
    raw = bytes(pkt)[:32]
    entropy_like = sum(raw) / (1 + len(raw))

    # inter-arrival time per IP (bounded to prevent unbounded growth)
    now = time.time()
    last = _last_seen.get(ip.src, now)
    inter_arrival = now - last
    _last_seen[ip.src] = now
    _last_seen.move_to_end(ip.src)
    if len(_last_seen) > ML_LAST_SEEN_MAX:
        _last_seen.popitem(last=False)

    #  broadcast or multicast 
    is_broadcast = 1 if ip.dst.endswith(".255") or ip.dst.startswith("224.") else 0

    return {
        "packet_size": size,
        "ip_total_length": ip_len,
        "protocol": protocol,
        "src_port": src_port,
        "dst_port": dst_port,
        "tcp_flags": tcp_flags,
        "ttl": ttl,
        "entropy_like": entropy_like,
        "inter_arrival": inter_arrival,
        "is_broadcast": is_broadcast
    }


def as_vector(feat: dict):
    """Ensure consistent numeric order for ML model."""
    return [feat[name] for name in FEATURE_NAMES]
