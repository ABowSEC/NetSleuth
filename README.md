#NetSleuth
A lightweight Python tool that passively monitors your local network. It shows active devices, their DNS queries, connections, and ARP activity. Without sending packets



- **Passive Network Monitoring** - Captures and analyzes network traffic without actively probing devices
- **Smart Device Identification** - Automatically identifies devices using multiple detection methods
- **Real-time Web Dashboard** - Beautiful, responsive web interface for live monitoring
- **Cross-platform Support** - Works on Windows, Linux, and macOS
- **Protocol Analysis** - Monitors DNS, TCP/UDP, ARP, and mDNS traffic
- **Behavioral Analysis** - Identifies device types based on network behavior patterns

## Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd NetSleuth
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run NetSleuth**
   ```bash
   # Basic monitoring
   python main.py
   
   # With web interface
   python main.py --web
   ```

## Usage Guide

### Command Line Options

```bash
python main.py [OPTIONS]

Options:
  --web, -w              Start web interface
  --interface, -i TEXT   Network interface to monitor
  --port, -p INTEGER     Web interface port (default: 5000)
  --help                 Show help message
```

### Examples

```bash
# Basic network monitoring
python main.py

# Start web interface on default port
python main.py --web

# Specify interface and custom port
python main.py --web --interface "Wi-Fi" --port 8080

# Monitor specific interface only
python main.py --interface "Ethernet"
```

## Configuration

### Debug Settings

Edit `config.py` to control debugging and verbosity:

```python
# Enable verbose packet logging (shows every packet)
VERBOSE = False

# Enable debug mode (shows additional diagnostic information)
DEBUG_MODE = False

# Web interface settings
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000

# Summary interval (seconds)
SUMMARY_INTERVAL = 30

# Web interface update interval (seconds)
WEB_UPDATE_INTERVAL = 5
```

### Device Configuration

Configure known devices in `src/config/known_devices.json`:

```json
{
  "ip": {
    "10.0.0.6": "My Laptop",
    "10.0.0.9": "LG TV"
  },
  "mac": {
    "74:e6:b8:d5:dd:36": "LG TV",
    "fc:fb:fb:12:34:56": "Amazon Echo"
  },
  "mac_prefix": {
    "74:e6:b8": "LG Electronics",
    "fc:fb:fb": "Amazon Technologies",
    "d8:96:e0": "Apple Inc."
  }
}
```

##  Device Identification

NetSleuth uses a multi-layered approach to identify devices:

### 1. Known Devices
- **IP-based**: Direct IP address mapping
- **MAC-based**: Specific MAC address mapping
- **MAC Prefix**: Manufacturer identification by MAC prefix

### 2. Behavioral Analysis
Automatically identifies device types based on network behavior:

- **Apple Devices**: AirPlay, companion-link services
- **Smart TVs**: LG webOS, Roku, Amazon Fire TV
- **Gaming Consoles**: Xbox, PlayStation
- **Smart Home**: HomeKit, Matter protocol
- **Mobile Devices**: Companion link services
- **Routers/Gateways**: Common gateway IPs
- **DNS Servers**: Known DNS server IPs

### 3. Fallback Identification
- **IP-based naming**: "Device (IP)" for unknown devices
- **Generic naming**: "Unknown Device" as last resort



### Core 

```
NetSleuth/
├── main.py                 # Entry point and CLI interface
├── config.py              # Configuration settings
├── requirements.txt       # Python dependencies
├── src/
│   ├── core/
│   │   ├── sniffer.py     # Cross-platform packet capture
│   │   ├── analyzer.py    # Protocol analysis and parsing
│   │   └── device_tracker.py # Device activity tracking
│   ├── utils/
│   │   ├── device_mapper.py # Device identification logic
│   │   └── network_utils.py # Network interface utilities
│   ├── web/
│   │   ├── web_interface.py # Flask web server
│   │   └── templates/
│   │       └── dashboard.html # Web dashboard
│   └── config/
│       └── known_devices.json # Device configuration
```

### Data Flow

1. **Packet Capture** → `sniffer.py` captures network packets
2. **Protocol Analysis** → `analyzer.py` parses packets and extracts data
3. **Device Tracking** → `device_tracker.py` maintains device activity logs
4. **Device Identification** → `device_mapper.py` identifies devices
5. **Web Interface** → `web_interface.py` serves real-time dashboard

##  Web Dashboard

### Features
- **Real-time Updates**: Auto-refreshes every 5 seconds
- **Device Overview**: Shows all detected devices with activity
- **Connection Statistics**: Tracks TCP/UDP connections
- **DNS Query Logging**: Monitors domain lookups
- **Service Discovery**: Tracks ARP and mDNS activity
- **Responsive Design**: Works on desktop and mobile

### Dashboard Sections
- **Statistics Cards**: Total devices, connections, DNS queries
- **Device Grid**: Individual device cards with detailed information
- **Activity Logs**: DNS queries, connections, and services per device

##  Technical Details

### Supported Protocols
- **DNS**: Domain name resolution queries
- **TCP**: Connection tracking and port monitoring
- **UDP**: Service discovery and communication
- **ARP**: Address resolution protocol
- **mDNS**: Multicast DNS for service discovery

### Cross-Platform Support

#### Windows
- Uses Npcap for packet capture
- Attempts L2 capture for MAC addresses
- Falls back to IP-only capture if needed

#### Linux/macOS
- Full Layer 2 packet capture
- Monitor mode support
- Fallback to IP-only if L2 fails

### Performance Considerations
- **Memory Efficient**: Doesn't store packet data, only metadata
- **CPU Optimized**: Minimal packet processing overhead
- **Network Friendly**: Passive monitoring, no network impact

## Troubleshooting

### Common Issues

#### No Devices Detected
1. **Check Interface**: Ensure correct network interface is selected
2. **Permissions**: Run as administrator/root if needed
3. **Firewall**: Ensure firewall allows packet capture
4. **Network Activity**: Generate some network traffic

#### MAC Addresses Show as "Unknown"
- **Windows**: May require administrator privileges
- **Linux**: May need to run with `sudo`
- **Interface**: Some interfaces don't support MAC capture

#### Web Interface Not Loading
1. **Port Check**: Ensure port isn't in use
2. **Firewall**: Check if firewall blocks the port
3. **Browser**: Try different browser or clear cache

### Debug Mode

Enable in `config.py`:
```python
DEBUG_MODE = True
VERBOSE = True
```

This will show:
- Packet processing details
- Device identification steps
- Error messages and warnings

## Monitoring Notes

### Network Security
- **Passive Only**: NetSleuth doesn't send packets, only observes
- **Privacy Respectful**: No packet content analysis, only metadata
- **Local Network**: Designed for monitoring your own network

### Performance Monitoring
- **Resource Usage**: Monitor CPU and memory usage
- **Network Impact**: Verify no impact on network performance
- **Storage**: Device logs are kept in memory, no disk usage

### Device Management
- **Regular Updates**: Keep known devices configuration updated
- **Behavioral Patterns**: Learn normal device behavior patterns
- **Anomaly Detection**: Watch for unusual device activity



- **Scapy**: Packet manipulation library
- **Flask**: Web framework for dashboard
- **Npcap**: Windows packet capture library

---

**NetSleuth** - Your network, under your surveillance 