import time

# Known devices mapping (expand as needed)
known_devices = {
    "10.0.0.6": "MyLaptop",
    "10.0.0.9": "LG TV",
    "74:e6:b8:d5:dd:36": "LG TV MAC"
}

device_log = {}  # Dynamic record of device activity

def update_device(ip, field, value):
    now = time.strftime('%H:%M:%S')
    if ip not in device_log:
        device_log[ip] = {
            "hostname": known_devices.get(ip, "UNKNOWN DEVICE"),
            "dns_queries": [],
            "connections": [],
            "services": [],
            "last_seen": now
        }

    if field == "dns_queries" and value not in device_log[ip][field]:
        device_log[ip][field].append(value)
    elif field == "connections" and value not in device_log[ip][field]:
        device_log[ip][field].append(value)
    elif field == "services" and value not in device_log[ip][field]:
        device_log[ip][field].append(value)

    device_log[ip]["last_seen"] = now

def print_summary():
    print("\n==================== NETWORK SUMMARY ====================")
    for ip, data in device_log.items():
        print(f"\n[Device: {data['hostname']}] {ip}")
        if data["dns_queries"]:
            print("  ▸ DNS Queries: " + ", ".join(data["dns_queries"]))
        if data["connections"]:
            print("  ▸ Connections: " + ", ".join(data["connections"]))
        if data["services"]:
            print("  ▸ Services: " + ", ".join(data["services"]))
        print(f"  ▸ Last seen: {data['last_seen']}")
    print("========================================================\n")
