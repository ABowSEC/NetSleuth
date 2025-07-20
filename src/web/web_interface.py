from flask import Flask, render_template, jsonify, request
from ..core.device_tracker import device_log
from ..core.alert_system import alert_system
import threading
import time
from datetime import datetime
import json

app = Flask(__name__)

# Global variable to store the latest network data
network_data = {
    'devices': {},
    'last_update': None,
    'total_devices': 0,
    'total_connections': 0,
    'total_dns_queries': 0,
    'alerts': []
}

def update_network_data():
    """Update the global network data from device_log"""
    global network_data
    
    devices = {}
    total_connections = 0
    total_dns_queries = 0
    
    for ip, data in device_log.items():
        devices[ip] = {
            'hostname': data.get('hostname', 'Unknown'),
            'mac': data.get('mac', 'Unknown'),
            'dns_queries': data.get('dns_queries', []),
            'connections': data.get('connections', []),
            'services': data.get('services', []),
            'last_seen': data.get('last_seen', 'Unknown'),
            'connection_count': len(data.get('connections', [])),
            'dns_count': len(data.get('dns_queries', []))
        }
        total_connections += len(data.get('connections', []))
        total_dns_queries += len(data.get('dns_queries', []))
    
    network_data['devices'] = devices
    network_data['last_update'] = datetime.now().strftime('%H:%M:%S')
    network_data['total_devices'] = len(devices)
    network_data['total_connections'] = total_connections
    network_data['total_dns_queries'] = total_dns_queries
    network_data['alerts'] = alert_system.get_alerts(50)  # Get last 50 alerts

def data_update_loop():
    """Background thread to continuously update network data"""
    while True:
        update_network_data()
        time.sleep(5)  # Update every 5 seconds

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/network-data')
def get_network_data():
    """API endpoint to get current network data"""
    return jsonify(network_data)

@app.route('/api/devices')
def get_devices():
    """API endpoint to get just the devices data"""
    return jsonify(network_data['devices'])

@app.route('/api/alerts')
def get_alerts():
    """API endpoint to get alerts"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(alert_system.get_alerts(limit))

@app.route('/api/alerts', methods=['POST'])
def create_alert():
    """API endpoint to create a custom alert"""
    data = request.get_json()
    alert_type = data.get('type', 'custom')
    severity = data.get('severity', 'MEDIUM')
    message = data.get('message', 'Custom alert')
    
    alert_system.create_alert(alert_type, severity, message, data.get('data'))
    return jsonify({'status': 'success', 'message': 'Alert created'})

@app.route('/api/alerts/clear', methods=['POST'])
def clear_alerts():
    """API endpoint to clear all alerts"""
    alert_system.clear_alerts()
    return jsonify({'status': 'success', 'message': 'Alerts cleared'})

@app.route('/api/alerts/export')
def export_alerts():
    """API endpoint to export alerts"""
    filename = request.args.get('filename')
    alert_system.export_alerts(filename)
    return jsonify({'status': 'success', 'message': 'Alerts exported'})

@app.route('/api/clear-data', methods=['POST'])
def clear_data():
    """API endpoint to clear all device data"""
    device_log.clear()
    return jsonify({'status': 'success', 'message': 'Data cleared'})

@app.route('/api/stop-monitoring', methods=['POST'])
def stop_monitoring():
    """API endpoint to stop monitoring (placeholder)"""
    # In a real implementation, this would signal the main thread to stop
    return jsonify({'status': 'success', 'message': 'Monitoring stopped'})

@app.route('/api/device/<ip>')
def get_device(ip):
    """API endpoint to get specific device data"""
    if ip in device_log:
        data = device_log[ip]
        return jsonify({
            'ip': ip,
            'hostname': data.get('hostname', 'Unknown'),
            'mac': data.get('mac', 'Unknown'),
            'dns_queries': data.get('dns_queries', []),
            'connections': data.get('connections', []),
            'services': data.get('services', []),
            'last_seen': data.get('last_seen', 'Unknown'),
            'connection_count': len(data.get('connections', [])),
            'dns_count': len(data.get('dns_queries', []))
        })
    else:
        return jsonify({'error': 'Device not found'}), 404

@app.route('/api/statistics')
def get_statistics():
    """API endpoint to get detailed statistics"""
    devices = network_data['devices']
    
    # Calculate statistics
    total_devices = len(devices)
    total_connections = sum(len(d.get('connections', [])) for d in devices.values())
    total_dns_queries = sum(len(d.get('dns_queries', [])) for d in devices.values())
    
    # Device types
    device_types = {}
    for device in devices.values():
        hostname = device.get('hostname', 'Unknown')
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
    
    # Top DNS queries
    all_dns = []
    for device in devices.values():
        all_dns.extend(device.get('dns_queries', []))
    
    dns_counts = {}
    for query in all_dns:
        dns_counts[query] = dns_counts.get(query, 0) + 1
    
    top_dns = sorted(dns_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Top connections
    all_connections = []
    for device in devices.values():
        all_connections.extend(device.get('connections', []))
    
    conn_counts = {}
    for conn in all_connections:
        conn_counts[conn] = conn_counts.get(conn, 0) + 1
    
    top_connections = sorted(conn_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return jsonify({
        'summary': {
            'total_devices': total_devices,
            'total_connections': total_connections,
            'total_dns_queries': total_dns_queries,
            'total_alerts': len(alert_system.get_alerts())
        },
        'device_types': device_types,
        'top_dns_queries': top_dns,
        'top_connections': top_connections,
        'last_update': network_data['last_update']
    })

@app.route('/api/search')
def search_devices():
    """API endpoint to search devices"""
    query = request.args.get('q', '').lower()
    if not query:
        return jsonify(network_data['devices'])
    
    results = {}
    for ip, device in network_data['devices'].items():
        if (query in ip.lower() or 
            query in device.get('hostname', '').lower() or
            query in device.get('mac', '').lower()):
            results[ip] = device
    
    return jsonify(results)

@app.route('/api/health')
def health_check():
    """API endpoint for health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'devices_count': network_data['total_devices'],
        'alerts_count': len(alert_system.get_alerts())
    })

def start_web_interface(host='0.0.0.0', port=5000):
    """Start the web interface"""
    # Start the background data update thread
    update_thread = threading.Thread(target=data_update_loop, daemon=True)
    update_thread.start()
    
    print(f"Starting NetSleuth Web Interface at http://localhost:{port}")
    print("Dashboard will show real-time network monitoring data")
    
    app.run(host=host, port=port, debug=False)

if __name__ == '__main__':
    start_web_interface() 