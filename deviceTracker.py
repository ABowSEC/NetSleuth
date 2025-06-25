# deviceTracker.py
import time
from device_mapper import get_hostname

# Dynamic record of device activity
device_log: dict[str, dict] = {}

def update_device(ip,mac,field,value):
    """Track activity for a device, keyed by IP and (optionally) MAC."""
    now = time.strftime('%H:%M:%S')

    # Initialize record if first time we’ve seen this IP
    if ip not in device_log:
        device_log[ip] = {
            "hostname": get_hostname(ip=ip, mac=mac),
            "mac": mac,
            "dns_queries": [],
            "connections": [],
            "services": [],
            "last_seen": now
        }

    # Append value to the appropriate list—ignore unknown field names
    if field in ("dns_queries", "connections", "services"):
        if value and value not in device_log[ip][field]:
            device_log[ip][field].append(value)

    # Update last-seen timestamp
    device_log[ip]["last_seen"] = now


def print_summary():
    print("\n==================== NETWORK SUMMARY ====================")
    for ip, data in device_log.items():
        print(f"\n[Device: {data['hostname']}] {ip}")
        if data.get("mac"):
            print(f"  ▸ MAC: {data['mac']}")
        if data["dns_queries"]:
            print("  ▸ DNS Queries: " + ", ".join(data["dns_queries"]))
        if data["connections"]:
            print("  ▸ Connections: " + ", ".join(data["connections"]))
        if data["services"]:
            print("  ▸ Services: " + ", ".join(data["services"]))
        print(f"  ▸ Last seen: {data['last_seen']}")
    print("========================================================\n")
