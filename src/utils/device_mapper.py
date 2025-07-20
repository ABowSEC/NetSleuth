# device_mapper.py
import json, os, re

CFG = os.path.join(os.path.dirname(__file__), "..", "config", "known_devices.json")

# Load configuration with error handling
try:
    with open(CFG, "r") as f:
        _data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    print(f"Warning: Could not load device configuration: {e}")
    _data = {"ip": {}, "mac": {}, "mac_prefix": {}}

_ip_lookup       = {k.lower(): v for k, v in _data.get("ip", {}).items()}
_mac_lookup      = {k.lower(): v for k, v in _data.get("mac", {}).items()}
_mac_prefix_lkp  = {k.lower(): v for k, v in _data.get("mac_prefix", {}).items()}

def normal(mac):
    """Normalize 74:e6:b8:d5:dd:36  OR 74-E6-B8-D5-DD-36 → 74:e6:b8:d5:dd:36"""
    if not mac:
        return None
    mac = mac.lower()
    return re.sub(r"[^0-9a-f]", ":", mac)

def identify_device_by_behavior(ip, dns_queries=None, connections=None):
    """Identify device type based on its network behavior patterns"""
    if not dns_queries:
        dns_queries = []
    if not connections:
        connections = []
    
    # Convert to lowercase for matching
    dns_lower = [q.lower() for q in dns_queries]
    conn_lower = [c.lower() for c in connections]
    
    # Apple devices
    if any('apple' in q for q in dns_lower) or any('_airplay' in q for q in dns_lower):
        return "Apple Device"
    
    # Smart TVs
    if any('webos' in q for q in dns_lower) or any('lg' in q for q in dns_lower):
        return "LG Smart TV"
    if any('roku' in q for q in dns_lower):
        return "Roku Device"
    if any('firetv' in q for q in dns_lower) or any('amazon' in q for q in dns_lower):
        return "Amazon Fire TV"
    
    # Gaming consoles
    if any('xbox' in q for q in dns_lower) or any('playstation' in q for q in dns_lower):
        return "Gaming Console"
    
    # Smart home devices
    if any('homekit' in q for q in dns_lower) or any('_matter' in q for q in dns_lower):
        return "Smart Home Device"
    if any('spotify' in q for q in dns_lower):
        return "Spotify Device"
    
    # Mobile devices
    if any('companion-link' in q for q in dns_lower):
        return "Mobile Device"
    
    # Routers/Gateways
    if ip in ['10.0.0.1', '192.168.1.1', '192.168.0.1']:
        return "Router/Gateway"
    
    # DNS servers
    if ip in ['8.8.8.8', '8.8.4.4', '1.1.1.1', '75.75.75.75']:
        return "DNS Server"
    
    return None

def get_hostname(ip=None, mac=None, dns_queries=None, connections=None):
    """Get device hostname from IP or MAC address, with behavioral analysis"""
    # Try IP lookup first
    if ip and ip.lower() in _ip_lookup:
        return _ip_lookup[ip.lower()]
    
    # Try MAC lookup
    if mac:
        mac = normal(mac)
        if mac and mac in _mac_lookup:
            return _mac_lookup[mac]
        
        # Try MAC prefix lookup
        if mac and len(mac.split(":")) >= 3:
            prefix = ":".join(mac.split(":")[:3])
            if prefix in _mac_prefix_lkp:
                return _mac_prefix_lkp[prefix]
    
    # Try behavioral identification
    if ip:
        behavior_id = identify_device_by_behavior(ip, dns_queries, connections)
        if behavior_id:
            return behavior_id
    
    # Generate a friendly name if we have an IP
    if ip:
        return f"Device ({ip})"
    
    return "Unknown Device"
