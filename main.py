from sniffer import start_sniffing
from utils import get_active_interfaces
from deviceTracker import print_summary
import threading
import time

def start_periodic_summary(interval=30):
    def summary_loop():
        while True:
            time.sleep(interval)
            print_summary()
    thread = threading.Thread(target=summary_loop, daemon=True)
    thread.start()

def main():
    try:
        interfaces = get_active_interfaces()

        if not interfaces:
            print("No active network interfaces found.")
            return

        if len(interfaces) == 1:
            selected_iface = interfaces[0]
            print(f"Auto-selecting interface: {selected_iface}")
        else:
            print("Multiple active interfaces found:")
            for idx, iface in enumerate(interfaces, start=1):
                print(f"{idx}. {iface}")
            try:
                choice = int(input("Select interface number to sniff on: "))
                selected_iface = interfaces[choice - 1]
            except (IndexError, ValueError):
                print("Invalid selection.")
                return

        print("Starting NetSleuth... summaries every 30 seconds.\n")
        start_periodic_summary()
        start_sniffing(interface=selected_iface, packet_count=0)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Exiting NetSleuth.\n")

if __name__ == "__main__":
    main()
