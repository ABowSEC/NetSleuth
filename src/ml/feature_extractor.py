# src/ml/feature_extractor.py

from typing import Dict, Any, List
from scapy.packet import Packet
from scapy.layers.inet import IP, TCP, UDP

FEATURE_NAMES = [
    "src_port",
    "dst_port",
    "length",
    "protocol",
    "tcp_flags",
    "ttl",
]


def extract_features(pkt: Packet) -> Dict[str, float] | None:
    """
    Extract a simple numeric feature vector from a Scapy packet.
    Returns None if we can't extract anything useful.
    """
    if not pkt.haslayer(IP):
        return None

    ip = pkt[IP]
    proto = ip.proto
    length = len(pkt)
    ttl = getattr(ip, "ttl", 0)

    src_port = 0
    dst_port = 0
    tcp_flags = 0

    if pkt.haslayer(TCP):
        tcp = pkt[TCP]
        src_port = tcp.sport
        dst_port = tcp.dport
        tcp_flags = int(tcp.flags)
        proto_id = 6  # TCP
    elif pkt.haslayer(UDP):
        udp = pkt[UDP]
        src_port = udp.sport
        dst_port = udp.dport
        proto_id = 17  # UDP
    else:
        proto_id = proto  # other protocols: ICMP, etc.

    return {
        "src_port": float(src_port),
        "dst_port": float(dst_port),
        "length": float(length),
        "protocol": float(proto_id),
        "tcp_flags": float(tcp_flags),
        "ttl": float(ttl),
    }


def as_vector(feature_dict: Dict[str, float]) -> List[float]:
    """Convert ordered feature dict to a vector list."""
    return [feature_dict[name] for name in FEATURE_NAMES]
