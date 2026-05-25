# feature_extractor.py
import math
import time
from collections import OrderedDict
from scapy.layers.inet import IP, TCP, UDP, ICMP
from scapy.packet import Packet, Raw

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
    "byte_entropy",
    "inter_arrival",
    "is_broadcast"
]


def _byte_entropy(data: bytes) -> float:
    """Shannon entropy of a byte sequence, range [0, 8]."""
    if not data:
        return 0.0
    freq = [0] * 256
    for b in data:
        freq[b] += 1
    n = len(data)
    h = 0.0
    for c in freq:
        if c:
            p = c / n
            h -= p * math.log2(p)
    return h

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

    # Shannon entropy of payload (0=structured, 8=random/encrypted)
    payload = bytes(pkt[Raw].load) if pkt.haslayer(Raw) else bytes(pkt)
    byte_entropy = _byte_entropy(payload[:256])

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
        "byte_entropy": byte_entropy,
        "inter_arrival": inter_arrival,
        "is_broadcast": is_broadcast
    }


def as_vector(feat: dict):
    """Ensure consistent numeric order for ML model."""
    return [feat[name] for name in FEATURE_NAMES]
