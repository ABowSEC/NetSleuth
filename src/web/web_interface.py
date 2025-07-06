from flask import Flask, render_template, jsonify
from ..core.device_tracker import device_log
import threading
import time
from datetime import datetime

app = Flask(__name__)

# Global variable to store the latest network data
network_data = {
    'devices': {},
    'last_update': None,
    'total_devices': 0,
    'total_connections': 0,
    'total_dns_queries': 0
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