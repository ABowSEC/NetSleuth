# sniffer.py
import platform
from scapy.all import sniff, conf, Ether, IP, ARP
from scapy.layers.inet import IP, TCP, UDP

from .analyzer import analyze_packet

from src.ml.feature_extractor import extract_features, as_vector
from src.ml.model_manager import TrafficAnomalyModel

from src.core.anomaly_store import anomaly_store, AnomalyEvent
from src.core.suspicious_devices import suspicious_tracker

from datetime import datetime

try:
    from scapy.all import L3RawSocket          # Linux/macOS only
except ImportError:
    L3RawSocket = None

ml_model = TrafficAnomalyModel.load()

VERBOSE = False
WINDOWS = platform.system() == "Windows"

def colored(text, color):
    _C = {"cyan": "\033[96m", "red": "\033[91m", "reset": "\033[0m"}
    return f"{_C[color]}{text}{_C['reset']}"

def packet_callback(pkt):
    if VERBOSE:
        print(colored(pkt.summary(), "cyan"))

    mac_src = pkt[Ether].src.lower() if pkt.haslayer(Ether) else None
    ip_src  = pkt[IP].src if pkt.haslayer(IP) else pkt[ARP].psrc if pkt.haslayer(ARP) else None
    ip_dst  = pkt[IP].dst if pkt.haslayer(IP) else pkt[ARP].pdst if pkt.haslayer(ARP) else None

    # ----- existing analysis pipeline -----
    analyze_packet(pkt, mac_src=mac_src, ip_src=ip_src, ip_dst=ip_dst)

    # ANOMALY  DETECTION
    feat_dict = extract_features(pkt)
    if feat_dict is None:
        return  # Not a packet type we extract from

    vec = as_vector(feat_dict)
    result = ml_model.predict_one(vec)

    if result is None:
        return  # No model loaded → ML disabled

    if result.is_anomaly:
        # Collect some packet metadata for the event
        src_port = 0
        dst_port = 0
        proto = "OTHER"

        if pkt.haslayer(TCP):
            src_port = int(pkt[TCP].sport)
            dst_port = int(pkt[TCP].dport)
            proto = "TCP"
        elif pkt.haslayer(UDP):
            src_port = int(pkt[UDP].sport)
            dst_port = int(pkt[UDP].dport)
            proto = "UDP"

        event = AnomalyEvent(
            timestamp=datetime.utcnow().isoformat(),
            src_ip=ip_src or "?",
            dst_ip=ip_dst or "?",
            src_port=src_port,
            dst_port=dst_port,
            protocol=proto,
            score=result.score,
            extra=feat_dict,
        )

        suspicious_tracker.register_anomaly(ip_src, result.score)
        anomaly_store.add(event)
        print(colored(
            f"[ML] Anomaly detected → {ip_src}:{src_port} → {ip_dst}:{dst_port} "
            f"(score={result.score:.3f})",
            "red"
        ))
def start_sniffing(interface, packet_count=0):
    # ---------- Windows: try L2 capture first, fall back to L3 ----------
    if WINDOWS:
        print("[i] Windows detected → attempting L2 capture for MAC addresses")
        
        try:
            # Try to get MAC addresses with L2 capture
            sniff(iface=interface,
                  prn=packet_callback,
                  count=packet_count,
                  store=False)
            return
        except Exception as e:
            print(colored(f"[!] L2 capture failed: {e}\n    Falling back to IP-only capture.", "red"))
            
            # Fallback to IP-only capture
            conf.use_pcap = True
            l3sock = conf.L3socket(iface=interface)
            sniff(
                opened_socket=l3sock,
                prn=packet_callback,
                count=packet_count,
                store=False,
                filter="ip"
            )
            return

    # ---------- Linux / macOS: try full L2, then fall back ----------
    try:
        sniff(iface=interface,
              prn=packet_callback,
              count=packet_count,
              store=False,
              monitor=True)
    except Exception as e:
        print(colored(f"[!] L2 sniffing failed: {e}\n    Falling back to IP-only.", "red"))
        if L3RawSocket:
            conf.L3socket = L3RawSocket
        sniff(iface=interface,
              prn=packet_callback,
              count=packet_count,
              store=False,
              filter="ip")