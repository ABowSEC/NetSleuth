from src.core.sniffer import start_sniffing
from src.utils.network_utils import get_active_interfaces
from src.core.device_tracker import print_summary
from src.web.web_interface import start_web_interface
import threading
import time
import argparse

def start_periodic_summary(interval=30):
    def summary_loop():
        while True:
            time.sleep(interval)
            print_summary()
    thread = threading.Thread(target=summary_loop, daemon=True)
    thread.start()

def main():
    parser = argparse.ArgumentParser(description='NetSleuth - Network Traffic Monitor')
    parser.add_argument('--web', action='store_true', help='Start web interface')
    parser.add_argument('--interface', '-i', help='Network interface to monitor')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Web interface port (default: 5000)')
    args = parser.parse_args()

    try:
        interfaces = get_active_interfaces()

        if not interfaces:
            print("No active network interfaces found.")
            return

        # Select interface
        if args.interface:
            if args.interface in interfaces:
                selected_iface = args.interface
            else:
                print(f"Interface '{args.interface}' not found. Available interfaces:")
                for iface in interfaces:
                    print(f"  - {iface}")
                return
        elif len(interfaces) == 1:
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
        
        # Start periodic summary
        start_periodic_summary()
        
        # Start web interface if requested
        if args.web:
            web_thread = threading.Thread(
                target=start_web_interface, 
                kwargs={'port': args.port}, 
                daemon=True
            )
            web_thread.start()
            print(f"🌐 Web interface started at http://localhost:{args.port}")
            print("📊 Open your browser to view the real-time dashboard\n")

        # Start sniffing
        start_sniffing(interface=selected_iface, packet_count=0)

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user. Exiting NetSleuth.\n")

if __name__ == "__main__":
    main()
