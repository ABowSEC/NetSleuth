# API Documentation

NetSleuth provides a RESTful API for accessing network monitoring data programmatically.

## Base URL

```
http://localhost:5000
```

## Authentication

Currently, the API does not require authentication. In production environments, consider implementing authentication.

## Endpoints

### 1. Dashboard

**GET** `/`

Returns the main dashboard HTML page.

**Response:**
- Content-Type: `text/html`
- Status: `200 OK`

**Example:**
```bash
curl http://localhost:5000/
```

### 2. Network Data

**GET** `/api/network-data`

Returns comprehensive network monitoring data including devices, statistics, and timestamps.

**Response:**
- Content-Type: `application/json`
- Status: `200 OK`

**Response Schema:**
```json
{
  "devices": {
    "10.0.0.6": {
      "hostname": "My Laptop",
      "mac": "aa:bb:cc:dd:ee:ff",
      "dns_queries": ["google.com", "github.com"],
      "connections": ["8.8.8.8:53", "140.82.112.25:443"],
      "services": ["ARP→10.0.0.1"],
      "last_seen": "14:30:25",
      "connection_count": 2,
      "dns_count": 2
    }
  },
  "last_update": "14:30:25",
  "total_devices": 15,
  "total_connections": 45,
  "total_dns_queries": 23
}
```

**Example:**
```bash
curl http://localhost:5000/api/network-data
```

### 3. Devices

**GET** `/api/devices`

Returns only the devices data without statistics.

**Response:**
- Content-Type: `application/json`
- Status: `200 OK`

**Response Schema:**
```json
{
  "10.0.0.6": {
    "hostname": "My Laptop",
    "mac": "aa:bb:cc:dd:ee:ff",
    "dns_queries": ["google.com"],
    "connections": ["8.8.8.8:53"],
    "services": ["ARP→10.0.0.1"],
    "last_seen": "14:30:25",
    "connection_count": 1,
    "dns_count": 1
  }
}
```

**Example:**
```bash
curl http://localhost:5000/api/devices
```

## Data Models

### Device Object

```json
{
  "hostname": "string",           // Device name/identifier
  "mac": "string",               // MAC address (or "Unknown")
  "dns_queries": ["string"],     // Array of DNS queries
  "connections": ["string"],     // Array of connections (IP:port)
  "services": ["string"],        // Array of services (ARP, mDNS, etc.)
  "last_seen": "string",         // Timestamp of last activity (HH:MM:SS)
  "connection_count": 0,         // Number of connections
  "dns_count": 0                 // Number of DNS queries
}
```

### Network Statistics

```json
{
  "total_devices": 0,            // Total number of devices
  "total_connections": 0,        // Total number of connections
  "total_dns_queries": 0,        // Total number of DNS queries
  "last_update": "string"        // Timestamp of last update (HH:MM:SS)
}
```

## Usage Examples

### Python

```python
import requests
import json

# Get network data
response = requests.get('http://localhost:5000/api/network-data')
data = response.json()

# Print device information
for ip, device in data['devices'].items():
    print(f"Device: {device['hostname']} ({ip})")
    print(f"  MAC: {device['mac']}")
    print(f"  DNS Queries: {device['dns_queries']}")
    print(f"  Connections: {device['connections']}")
    print(f"  Last Seen: {device['last_seen']}")

# Print statistics
print(f"Total Devices: {data['total_devices']}")
print(f"Total Connections: {data['total_connections']}")
print(f"Total DNS Queries: {data['total_dns_queries']}")
```

### JavaScript

```javascript
// Get network data
fetch('http://localhost:5000/api/network-data')
  .then(response => response.json())
  .then(data => {
    console.log('Network Statistics:', {
      devices: data.total_devices,
      connections: data.total_connections,
      dnsQueries: data.total_dns_queries
    });
    
    // Process devices
    Object.entries(data.devices).forEach(([ip, device]) => {
      console.log(`Device: ${device.hostname} (${ip})`);
      console.log(`  MAC: ${device.mac}`);
      console.log(`  DNS Queries: ${device.dns_queries.length}`);
      console.log(`  Connections: ${device.connections.length}`);
    });
  })
  .catch(error => console.error('Error:', error));
```

### PowerShell

```powershell
# Get network data
$response = Invoke-RestMethod -Uri "http://localhost:5000/api/network-data" -Method GET

# Display statistics
Write-Host "Network Statistics:"
Write-Host "  Total Devices: $($response.total_devices)"
Write-Host "  Total Connections: $($response.total_connections)"
Write-Host "  Total DNS Queries: $($response.total_dns_queries)"

# Display devices
$response.devices | ForEach-Object {
    $device = $_.PSObject.Properties.Value
    Write-Host "Device: $($device.hostname) ($($device.ip))"
    Write-Host "  MAC: $($device.mac)"
    Write-Host "  DNS Queries: $($device.dns_queries.Count)"
    Write-Host "  Connections: $($device.connections.Count)"
}
```

### Bash

```bash
# Get network data
curl -s http://localhost:5000/api/network-data | jq '.'

# Get specific device information
curl -s http://localhost:5000/api/network-data | jq '.devices["10.0.0.6"]'

# Get statistics only
curl -s http://localhost:5000/api/network-data | jq '{total_devices, total_connections, total_dns_queries}'

# Monitor devices in real-time
watch -n 5 'curl -s http://localhost:5000/api/network-data | jq ".total_devices"'
```

## Real-time Monitoring

### Polling

For real-time monitoring, poll the API endpoints at regular intervals:

```python
import time
import requests

def monitor_network():
    while True:
        try:
            response = requests.get('http://localhost:5000/api/network-data')
            data = response.json()
            
            print(f"Devices: {data['total_devices']}, "
                  f"Connections: {data['total_connections']}, "
                  f"DNS: {data['total_dns_queries']}")
            
            time.sleep(5)  # Poll every 5 seconds
            
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            time.sleep(10)  # Wait longer on error

monitor_network()
```

### WebSocket (Future Enhancement)

Future versions may include WebSocket support for real-time updates:

```javascript
// Future implementation
const ws = new WebSocket('ws://localhost:5000/ws');

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Real-time update:', data);
};
```

## Error Handling

### HTTP Status Codes

- `200 OK` - Request successful
- `404 Not Found` - Endpoint not found
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
  "error": "Error message",
  "status": 500,
  "timestamp": "2024-01-15T14:30:25"
}
```

### Handling Errors

```python
import requests

try:
    response = requests.get('http://localhost:5000/api/network-data')
    response.raise_for_status()  # Raise exception for 4XX/5XX status codes
    data = response.json()
except requests.exceptions.HTTPError as e:
    print(f"HTTP Error: {e}")
except requests.exceptions.ConnectionError as e:
    print(f"Connection Error: {e}")
except requests.exceptions.Timeout as e:
    print(f"Timeout Error: {e}")
except requests.exceptions.RequestException as e:
    print(f"Request Error: {e}")
```

## Rate Limiting

Currently, there are no rate limits on the API. In production environments, consider implementing rate limiting to prevent abuse.

## CORS

The API supports CORS for cross-origin requests. Configure CORS settings in the web interface if needed.

## Security Considerations

1. **Authentication**: Implement authentication for production use
2. **HTTPS**: Use HTTPS in production environments
3. **Access Control**: Restrict API access to authorized clients
4. **Input Validation**: Validate all input parameters
5. **Rate Limiting**: Implement rate limiting to prevent abuse

## Future Enhancements

Planned API enhancements:

1. **Authentication endpoints** - User management
2. **Device management** - Add/remove known devices
3. **Configuration endpoints** - Modify settings via API
4. **Historical data** - Access historical monitoring data
5. **Alerts** - Configure and manage alerts
6. **Export functionality** - Export data in various formats 