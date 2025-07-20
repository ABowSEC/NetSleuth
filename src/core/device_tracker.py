# deviceTracker.py
import time
from ..utils.device_mapper import get_hostname

# Dynamic record of device activity
device_log: dict[str, dict] = {}

def update_device(ip, mac, field, value):
    """Track activity for a device, keyed by IP and (optionally) MAC."""
    if not ip:  # Skip if no IP provided
        return
        
    now = time.strftime('%H:%M:%S')

    # Initialize record if first time we've seen this IP
    if ip not in device_log:
        device_log[ip] = {
            "hostname": get_hostname(ip=ip, mac=mac),
            "mac": mac or "Unknown",
            "dns_queries": [],
            "connections": [],
            "services": [],
            "last_seen": now
        }
    else:
        # Update MAC if we have a new one and didn't have one before
        if mac and device_log[ip]["mac"] == "Unknown":
            device_log[ip]["mac"] = mac
        
        # Re-evaluate hostname with current data for better identification
        device_log[ip]["hostname"] = get_hostname(
            ip=ip, 
            mac=device_log[ip]["mac"], 
            dns_queries=device_log[ip]["dns_queries"],
            connections=device_log[ip]["connections"]
        )

    # Append value to the appropriate list—ignore unknown field names
    if field in ("dns_queries", "connections", "services"):
        if value and value not in device_log[ip][field]:
            device_log[ip][field].append(value)

    # Update timestamp
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
