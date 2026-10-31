# deviceTracker.py
from datetime import datetime, timedelta
from ..utils.device_mapper import get_hostname
from .alert_system import alert_system
from .persistence import load_devices, save_device
from .known_registry import is_known, get_name

from ..constants import (
    MAX_CONNECTIONS_PER_DEVICE,
    MAX_DNS_QUERIES_PER_DEVICE,
    DEVICE_STALE_HOURS,
)

# Global device activity log — pre-populated from persistent storage
device_log = load_devices()

def update_device(ip, mac, field, value):
    """Update device log with new activity."""
    now = datetime.now().isoformat()

    # Initialize device entry if not exists
    if ip not in device_log:
        known = is_known(mac)
        device_log[ip] = {
            'hostname':      get_hostname(ip=ip, mac=mac),
            'mac':           mac or 'Unknown',
            'dns_queries':   [],
            'connections':   [],
            'services':      [],
            'first_seen':    now,
            'last_seen':     now,
            'is_known':      known,
            'friendly_name': get_name(mac) or '',
        }

        # Only alert for genuinely unknown devices
        if not known:
            alert_system.check_new_device(ip, mac, device_log)

    # Update last seen time
    device_log[ip]['last_seen'] = now
    
    # Update hostname if we have new information
    if field == 'hostname' and value:
        device_log[ip]['hostname'] = value
    elif field == 'mac' and value and value != 'Unknown':
        device_log[ip]['mac'] = value
        # Update hostname with new MAC info
        device_log[ip]['hostname'] = get_hostname(ip=ip, mac=value)
    
    # Handle different field types
    if field == 'dns_queries':
        if value not in device_log[ip]['dns_queries']:
            device_log[ip]['dns_queries'].append(value)
            alert_system.check_suspicious_dns(ip, device_log[ip]['dns_queries'])
            alert_system.check_data_exfiltration(ip, device_log[ip]['dns_queries'])

    elif field == 'connections':
        if value not in device_log[ip]['connections']:
            device_log[ip]['connections'].append(value)
            alert_system.check_high_connection_rate(ip, device_log[ip]['connections'])
            alert_system.check_port_scan(ip, device_log[ip]['connections'])
    
    elif field == 'services':
        if value not in device_log[ip]['services']:
            device_log[ip]['services'].append(value)
    
    # Limit list sizes using config values
    if len(device_log[ip]['dns_queries']) > MAX_DNS_QUERIES_PER_DEVICE:
        device_log[ip]['dns_queries'] = device_log[ip]['dns_queries'][-MAX_DNS_QUERIES_PER_DEVICE:]

    if len(device_log[ip]['connections']) > MAX_CONNECTIONS_PER_DEVICE:
        device_log[ip]['connections'] = device_log[ip]['connections'][-MAX_CONNECTIONS_PER_DEVICE:]

    if len(device_log[ip]['services']) > 50:
        device_log[ip]['services'] = device_log[ip]['services'][-50:]

    save_device(ip, device_log[ip])

def get_device_summary():
    """Get a summary of all devices."""
    summary = []
    for ip, data in list(device_log.items()):
        summary.append({
            'ip': ip,
            'hostname': data.get('hostname', 'Unknown'),
            'mac': data.get('mac', 'Unknown'),
            'connection_count': len(data.get('connections', [])),
            'dns_count': len(data.get('dns_queries', [])),
            'last_seen': data.get('last_seen', 'Unknown')
        })
    return summary

def get_network_statistics():
    """Get comprehensive network statistics."""
    snapshot = list(device_log.values())
    total_devices = len(snapshot)
    total_connections = sum(len(d.get('connections', [])) for d in snapshot)
    total_dns_queries = sum(len(d.get('dns_queries', [])) for d in snapshot)
    total_services = sum(len(d.get('services', [])) for d in snapshot)

    # Device type breakdown
    device_types = {}
    for data in snapshot:
        hostname = data.get('hostname', 'Unknown')
        if 'Apple' in hostname:
            device_types['Apple'] = device_types.get('Apple', 0) + 1
        elif 'Smart TV' in hostname:
            device_types['Smart TV'] = device_types.get('Smart TV', 0) + 1
        elif 'Router' in hostname:
            device_types['Router'] = device_types.get('Router', 0) + 1
        elif 'DNS Server' in hostname:
            device_types['DNS Server'] = device_types.get('DNS Server', 0) + 1
        else:
            device_types['Other'] = device_types.get('Other', 0) + 1
    
    # Real-time statistics
    statistics = {
        'total_devices': total_devices,
        'total_connections': total_connections,
        'total_dns_queries': total_dns_queries,
        'total_services': total_services,
        'device_types': device_types,
        'active_alerts': len(alert_system.get_alerts())
    }
    
    return statistics

def purge_stale_devices():
    """Remove devices not seen within DEVICE_STALE_HOURS."""
    cutoff = datetime.now() - timedelta(hours=DEVICE_STALE_HOURS)
    stale = [
        ip for ip, data in list(device_log.items())
        if _parse_last_seen(data.get('last_seen', '')) < cutoff
    ]
    for ip in stale:
        del device_log[ip]
    if stale:
        print(f"[Tracker] Purged {len(stale)} stale device(s).")

def _parse_last_seen(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return datetime.min

def print_summary():
    
    print("\n==================== NETWORK SUMMARY ====================")
    for ip, data in list(device_log.items()):
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
