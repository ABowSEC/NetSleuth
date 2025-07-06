# sniffer.py
import platform
from scapy.all import sniff, conf, Ether, IP, ARP
from .analyzer import analyze_packet

try:
    from scapy.all import L3RawSocket          # Linux/macOS only
except ImportError:
    L3RawSocket = None

VERBOSE = False
WIN_OS = platform.system() == "Windows"

def colored(text, color):
    _C = {"cyan": "\033[96m", "red": "\033[91m", "reset": "\033[0m"}
    return f"{_C[color]}{text}{_C['reset']}"

def packet_callback(pkt):
    if VERBOSE:
        print(colored(pkt.summary(), "cyan"))

    mac_src = pkt[Ether].src.lower() if pkt.haslayer(Ether) else None
    ip_src  = pkt[IP].src if pkt.haslayer(IP) else pkt[ARP].psrc if pkt.haslayer(ARP) else None
    ip_dst  = pkt[IP].dst if pkt.haslayer(IP) else pkt[ARP].pdst if pkt.haslayer(ARP) else None
    analyze_packet(pkt, mac_src=mac_src, ip_src=ip_src, ip_dst=ip_dst)

def start_sniffing(interface, packet_count=0):
    # ---------- Windows: force Layer-3 socket ----------
    if WIN_OS:
        conf.use_pcap = True                     # Npcap raw-IP mode
        print("[i] Windows detected → using IP-level capture only")

        # Build a Layer-3 socket and give it to sniff()
        l3sock = conf.L3socket(iface=interface)
        sniff(
            opened_socket=l3sock,                # <- key trick
            prn=packet_callback,
            count=packet_count,
            store=False,
            filter="ip"                          # keeps it lean
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