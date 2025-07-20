# deviceTracker.py
import time
from ..utils.device_mapper import get_hostname
from .alert_system import alert_system

# Global device activity log
device_log = {}

def update_device(ip, mac, field, value):
    """Update device log with new activity."""
    now = time.strftime('%H:%M:%S')
    
    # Initialize device entry if not exists
    if ip not in device_log:
        device_log[ip] = {
            'hostname': get_hostname(ip=ip, mac=mac),
            'mac': mac or 'Unknown',
            'dns_queries': [],
            'connections': [],
            'services': [],
            'last_seen': now
        }
        
        # Check for new device alert
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
            # Check for suspicious DNS queries
            alert_system.check_suspicious_dns(ip, device_log[ip]['dns_queries'])
    
    elif field == 'connections':
        if value not in device_log[ip]['connections']:
            device_log[ip]['connections'].append(value)
            # Check for high connection rates
            alert_system.check_high_connection_rate(ip, device_log[ip]['connections'])
            # Check for port scanning
            alert_system.check_port_scan(ip, device_log[ip]['connections'])
            # Check for data exfiltration
            alert_system.check_data_exfiltration(ip, device_log[ip]['connections'])
    
    elif field == 'services':
        if value not in device_log[ip]['services']:
            device_log[ip]['services'].append(value)
    
    # Limit the size of lists to prevent memory issues
    if len(device_log[ip]['dns_queries']) > 100:
        device_log[ip]['dns_queries'] = device_log[ip]['dns_queries'][-100:]
    
    if len(device_log[ip]['connections']) > 100:
        device_log[ip]['connections'] = device_log[ip]['connections'][-100:]
    
    if len(device_log[ip]['services']) > 50:
        device_log[ip]['services'] = device_log[ip]['services'][-50:]

def get_device_summary():
    """Get a summary of all devices."""
    summary = []
    for ip, data in device_log.items():
        summary.append({
            'ip': ip,
            'hostname': data.get('hostname', 'Unknown'),
            'mac': data.get('mac', 'Unknown'),
            'connection_count': len(data.get('connections', [])),
            'dns_count': len(data.get('dns_queries', [])),
            'last_seen': data.get('last_seen', 'Unknown')
        })
    return summary

def cleanup_old_devices(timeout_minutes=60):
    """Remove devices that haven't been seen recently."""
    current_time = time.time()
    timeout_seconds = timeout_minutes * 60
    
    devices_to_remove = []
    for ip, data in device_log.items():
        last_seen_str = data.get('last_seen', '00:00:00')
        try:
            # Parse time string to timestamp
            time_parts = last_seen_str.split(':')
            if len(time_parts) == 3:
                hours, minutes, seconds = map(int, time_parts)
                # Calculate seconds since midnight
                last_seen_seconds = hours * 3600 + minutes * 60 + seconds
                current_seconds = int(current_time % 86400)  # Seconds since midnight
                
                # Handle day wrap-around
                if current_seconds < last_seen_seconds:
                    current_seconds += 86400
                
                if (current_seconds - last_seen_seconds) > timeout_seconds:
                    devices_to_remove.append(ip)
        except (ValueError, IndexError):
            # If we can't parse the time, keep the device
            continue
    
    # Remove old devices
    for ip in devices_to_remove:
        del device_log[ip]
        alert_system.create_alert(
            'device_timeout',
            'LOW',
            f"Device {ip} timed out and was removed",
            {'ip': ip, 'timeout_minutes': timeout_minutes}
        )

def get_network_statistics():
    """Get comprehensive network statistics."""
    total_devices = len(device_log)
    total_connections = sum(len(d.get('connections', [])) for d in device_log.values())
    total_dns_queries = sum(len(d.get('dns_queries', [])) for d in device_log.values())
    total_services = sum(len(d.get('services', [])) for d in device_log.values())
    
    # Device type breakdown
    device_types = {}
    for data in device_log.values():
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
    
    # Device type breakdown, top queries, connection patterns
    # This part is not provided in the original code or the new code block
    # It's assumed to be implemented here
    
    return statistics

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
