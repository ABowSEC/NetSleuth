# alert_system.py
import time
import json
from datetime import datetime
from typing import Dict, List, Callable
from ..utils.device_mapper import get_hostname

class AlertSystem:
    """Network monitoring alert system for security and performance events"""
    
    def __init__(self):
        self.alerts = []
        self.alert_handlers = []
        self.alert_rules = {
            'new_device': True,
            'suspicious_dns': True,
            'high_connection_rate': True,
            'unknown_device': True,
            'port_scan': True,
            'data_exfiltration': True
        }
        
    def add_alert_handler(self, handler: Callable):
        """Add a custom alert handler function"""
        self.alert_handlers.append(handler)
    
    def create_alert(self, alert_type: str, severity: str, message: str, data: Dict = None):
        """Create and process a new alert"""
        alert = {
            'timestamp': datetime.now().isoformat(),
            'type': alert_type,
            'severity': severity,  # LOW, MEDIUM, HIGH, CRITICAL
            'message': message,
            'data': data or {}
        }
        
        self.alerts.append(alert)
        
        # Call alert handlers
        for handler in self.alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                print(f"Alert handler error: {e}")
        
        # Print alert
        self._print_alert(alert)
    
    def _print_alert(self, alert):
        """Print formatted alert"""
        colors = {
            'LOW': '\033[94m',      # Blue
            'MEDIUM': '\033[93m',   # Yellow
            'HIGH': '\033[91m',     # Red
            'CRITICAL': '\033[95m'  # Magenta
        }
        
        color = colors.get(alert['severity'], '\033[0m')
        reset = '\033[0m'
        
        print(f"{color}[ALERT] {alert['severity']}: {alert['message']}{reset}")
    
    def check_new_device(self, ip: str, mac: str, device_log: Dict):
        """Check for new device alerts"""
        if not self.alert_rules['new_device']:
            return
            
        if ip not in device_log:
            hostname = get_hostname(ip=ip, mac=mac)
            self.create_alert(
                'new_device',
                'MEDIUM',
                f"New device detected: {hostname} ({ip})",
                {'ip': ip, 'mac': mac, 'hostname': hostname}
            )
    
    def check_suspicious_dns(self, ip: str, dns_queries: List[str]):
        """Check for suspicious DNS queries"""
        if not self.alert_rules['suspicious_dns']:
            return
            
        suspicious_domains = [
            'malware', 'virus', 'trojan', 'botnet', 'c2', 'command',
            'control', 'exfil', 'data', 'steal', 'crypto', 'mining'
        ]
        
        for query in dns_queries:
            query_lower = query.lower()
            for suspicious in suspicious_domains:
                if suspicious in query_lower:
                    self.create_alert(
                        'suspicious_dns',
                        'HIGH',
                        f"Suspicious DNS query from {ip}: {query}",
                        {'ip': ip, 'query': query, 'suspicious_term': suspicious}
                    )
                    break
    
    def check_high_connection_rate(self, ip: str, connections: List[str], threshold: int = 50):
        """Check for unusually high connection rates"""
        if not self.alert_rules['high_connection_rate']:
            return
            
        if len(connections) > threshold:
            self.create_alert(
                'high_connection_rate',
                'MEDIUM',
                f"High connection rate from {ip}: {len(connections)} connections",
                {'ip': ip, 'connection_count': len(connections), 'threshold': threshold}
            )
    
    def check_port_scan(self, ip: str, connections: List[str]):
        """Detect potential port scanning activity"""
        if not self.alert_rules['port_scan']:
            return
            
        # Extract unique ports
        ports = set()
        for conn in connections:
            if ':' in conn:
                try:
                    port = int(conn.split(':')[-1])
                    ports.add(port)
                except ValueError:
                    continue
        
        # Alert if many different ports are accessed
        if len(ports) > 20:
            self.create_alert(
                'port_scan',
                'HIGH',
                f"Potential port scan from {ip}: {len(ports)} different ports",
                {'ip': ip, 'ports': list(ports), 'port_count': len(ports)}
            )
    
    def check_data_exfiltration(self, ip: str, connections: List[str]):
        """Detect potential data exfiltration patterns"""
        if not self.alert_rules['data_exfiltration']:
            return
            
        # Check for connections to known data exfiltration services
        exfil_indicators = [
            'pastebin.com', 'github.com', 'gist.github.com',
            'dropbox.com', 'drive.google.com', 'mega.nz'
        ]
        
        for conn in connections:
            for indicator in exfil_indicators:
                if indicator in conn.lower():
                    self.create_alert(
                        'data_exfiltration',
                        'CRITICAL',
                        f"Potential data exfiltration from {ip} to {indicator}",
                        {'ip': ip, 'destination': conn, 'indicator': indicator}
                    )
    
    def get_alerts(self, limit: int = 100) -> List[Dict]:
        """Get recent alerts"""
        return self.alerts[-limit:]
    
    def clear_alerts(self):
        """Clear all alerts"""
        self.alerts.clear()
    
    def export_alerts(self, filename: str = None):
        """Export alerts to JSON file"""
        if not filename:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"alerts_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.alerts, f, indent=2)
        
        print(f"Alerts exported to {filename}")

# Global alert system instance
alert_system = AlertSystem() 