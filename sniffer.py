from scapy.all import sniff, conf
from analyzer import analyze_packet

VERBOSE = False  # Set to True to enable packet summaries

def colored(text, color):
    colors = {
        "magenta": "\033[95m", "blue": "\033[94m", "green": "\033[92m",
        "yellow": "\033[93m", "red": "\033[91m", "cyan": "\033[96m", "reset": "\033[0m"
    }
    return f"{colors[color]}{text}{colors['reset']}"

def packet_callback(packet):
    if VERBOSE:
        print(colored(packet.summary(), "cyan"))
    analyze_packet(packet)

def start_sniffing(interface, packet_count=0):
    try:
        if VERBOSE:
            print(colored(f"Trying Layer 2 sniffing on {interface}...", "green"))
        sniff(iface=interface, prn=packet_callback, count=packet_count)
    except Exception as e:
        if VERBOSE:
            print(colored(f"Layer 2 sniffing failed: {e}", "red"))
            print(colored("Falling back to Layer 3 (IP only)...", "yellow"))
        conf.use_pcap = True
        sniff(iface=interface, prn=packet_callback, count=packet_count, store=False, filter="ip")
