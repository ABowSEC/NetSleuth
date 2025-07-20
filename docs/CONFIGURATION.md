# Configuration Guide

This guide covers all configuration options available in NetSleuth, from basic settings to advanced customization.

## Configuration Files

### 1. Main Configuration (`config.py`)

The main configuration file controls debugging, web interface settings, and timing intervals.

```python
# NetSleuth Configuration
# Set these to True to enable debugging and verbose output

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

#### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `VERBOSE` | bool | `False` | Enable detailed packet logging |
| `DEBUG_MODE` | bool | `False` | Enable debug output and diagnostics |
| `WEB_HOST` | str | `'0.0.0.0'` | Web interface host address |
| `WEB_PORT` | int | `5000` | Web interface port number |
| `SUMMARY_INTERVAL` | int | `30` | Console summary update interval (seconds) |
| `WEB_UPDATE_INTERVAL` | int | `5` | Web dashboard update interval (seconds) |

### 2. Device Configuration (`src/config/known_devices.json`)

Configure known devices for better identification and naming.

```json
{
  "ip": {
    "10.0.0.6": "My Laptop",
    "10.0.0.9": "LG TV",
    "192.168.1.1": "Router"
  },
  "mac": {
    "74:e6:b8:d5:dd:36": "LG TV",
    "fc:fb:fb:12:34:56": "Amazon Echo",
    "aa:bb:cc:dd:ee:ff": "My Phone"
  },
  "mac_prefix": {
    "74:e6:b8": "LG Electronics",
    "fc:fb:fb": "Amazon Technologies",
    "d8:96:e0": "Apple Inc.",
    "00:50:56": "VMware Inc.",
    "52:54:00": "QEMU Virtual"
  }
}
```

#### Configuration Sections

##### IP-based Mapping
```json
"ip": {
  "192.168.1.100": "Device Name"
}
```
- Maps specific IP addresses to device names
- Highest priority in device identification
- Useful for static IP devices

##### MAC-based Mapping
```json
"mac": {
  "aa:bb:cc:dd:ee:ff": "Device Name"
}
```
- Maps specific MAC addresses to device names
- Medium priority in device identification
- Useful for devices with changing IPs

##### MAC Prefix Mapping
```json
"mac_prefix": {
  "aa:bb:cc": "Manufacturer Name"
}
```
- Maps MAC address prefixes to manufacturer names
- Lower priority in device identification
- Useful for identifying device types

## Advanced Configuration

### 1. Packet Capture Settings

Modify `src/core/sniffer.py` for advanced packet capture configuration:

```python
# Packet capture settings
PACKET_FILTER = "ip"  # BPF filter for packet capture
CAPTURE_TIMEOUT = 0   # Capture timeout (0 = infinite)
STORE_PACKETS = False # Store packet data in memory

# Windows-specific settings
WINDOWS_L2_CAPTURE = True  # Attempt L2 capture on Windows
WINDOWS_FALLBACK_L3 = True # Fallback to L3 if L2 fails

# Linux/macOS settings
LINUX_MONITOR_MODE = True  # Use monitor mode if available
LINUX_PROMISCUOUS = False  # Enable promiscuous mode
```

### 2. Protocol Analysis Settings

Configure protocol analysis in `src/core/analyzer.py`:

```python
# Protocol analysis settings
ANALYZE_DNS = True      # Analyze DNS queries
ANALYZE_TCP = True      # Analyze TCP connections
ANALYZE_UDP = True      # Analyze UDP traffic
ANALYZE_ARP = True      # Analyze ARP traffic
ANALYZE_MDNS = True     # Analyze mDNS traffic

# DNS analysis settings
DNS_QUERY_TIMEOUT = 30  # DNS query timeout (seconds)
DNS_MAX_QUERIES = 100   # Maximum DNS queries per device

# Connection tracking settings
CONNECTION_TIMEOUT = 300 # Connection timeout (seconds)
MAX_CONNECTIONS = 50    # Maximum connections per device
```

### 3. Device Tracking Settings

Configure device tracking in `src/core/device_tracker.py`:

```python
# Device tracking settings
DEVICE_TIMEOUT = 3600   # Device timeout (seconds)
MAX_DEVICES = 1000      # Maximum devices to track
CLEANUP_INTERVAL = 300  # Cleanup interval (seconds)

# Activity logging settings
LOG_DNS_QUERIES = True  # Log DNS queries
LOG_CONNECTIONS = True  # Log connections
LOG_SERVICES = True     # Log service discovery
LOG_TIMESTAMPS = True   # Log timestamps
```

## Environment Variables

You can override configuration settings using environment variables:

```bash
# Set environment variables
export NETSLEUTH_VERBOSE=true
export NETSLEUTH_DEBUG_MODE=true
export NETSLEUTH_WEB_PORT=8080
export NETSLEUTH_WEB_HOST=127.0.0.1

# Run NetSleuth
python main.py --web
```

### Supported Environment Variables

| Variable | Config Option | Type | Description |
|----------|---------------|------|-------------|
| `NETSLEUTH_VERBOSE` | `VERBOSE` | bool | Enable verbose logging |
| `NETSLEUTH_DEBUG_MODE` | `DEBUG_MODE` | bool | Enable debug mode |
| `NETSLEUTH_WEB_HOST` | `WEB_HOST` | str | Web interface host |
| `NETSLEUTH_WEB_PORT` | `WEB_PORT` | int | Web interface port |
| `NETSLEUTH_SUMMARY_INTERVAL` | `SUMMARY_INTERVAL` | int | Summary interval |
| `NETSLEUTH_WEB_UPDATE_INTERVAL` | `WEB_UPDATE_INTERVAL` | int | Web update interval |

## Configuration Examples

### 1. Development Configuration

```python
# config.py - Development settings
VERBOSE = True
DEBUG_MODE = True
WEB_HOST = '127.0.0.1'
WEB_PORT = 5000
SUMMARY_INTERVAL = 10
WEB_UPDATE_INTERVAL = 2
```

### 2. Production Configuration

```python
# config.py - Production settings
VERBOSE = False
DEBUG_MODE = False
WEB_HOST = '0.0.0.0'
WEB_PORT = 8080
SUMMARY_INTERVAL = 60
WEB_UPDATE_INTERVAL = 10
```

### 3. High-Performance Configuration

```python
# config.py - High-performance settings
VERBOSE = False
DEBUG_MODE = False
WEB_HOST = '0.0.0.0'
WEB_PORT = 5000
SUMMARY_INTERVAL = 120
WEB_UPDATE_INTERVAL = 30
```

### 4. Debug Configuration

```python
# config.py - Debug settings
VERBOSE = True
DEBUG_MODE = True
WEB_HOST = '127.0.0.1'
WEB_PORT = 5001
SUMMARY_INTERVAL = 5
WEB_UPDATE_INTERVAL = 1
```

## Device Configuration Examples

### 1. Home Network Configuration

```json
{
  "ip": {
    "192.168.1.1": "Router",
    "192.168.1.100": "My Laptop",
    "192.168.1.101": "My Phone",
    "192.168.1.102": "Smart TV"
  },
  "mac": {
    "aa:bb:cc:dd:ee:ff": "My Laptop",
    "11:22:33:44:55:66": "My Phone",
    "74:e6:b8:d5:dd:36": "LG Smart TV"
  },
  "mac_prefix": {
    "74:e6:b8": "LG Electronics",
    "fc:fb:fb": "Amazon Technologies",
    "d8:96:e0": "Apple Inc.",
    "00:50:56": "VMware Inc."
  }
}
```

### 2. Office Network Configuration

```json
{
  "ip": {
    "10.0.0.1": "Gateway",
    "10.0.0.10": "File Server",
    "10.0.0.20": "Print Server",
    "10.0.0.100": "Workstation 1",
    "10.0.0.101": "Workstation 2"
  },
  "mac": {
    "00:11:22:33:44:55": "File Server",
    "aa:bb:cc:dd:ee:ff": "Workstation 1"
  },
  "mac_prefix": {
    "00:50:56": "VMware Inc.",
    "52:54:00": "QEMU Virtual",
    "08:00:27": "VirtualBox"
  }
}
```

### 3. IoT Network Configuration

```json
{
  "ip": {
    "192.168.1.1": "Router",
    "192.168.1.10": "Smart Hub"
  },
  "mac": {
    "fc:fb:fb:12:34:56": "Amazon Echo",
    "74:e6:b8:d5:dd:36": "LG Smart TV",
    "aa:bb:cc:dd:ee:ff": "Smart Bulb"
  },
  "mac_prefix": {
    "fc:fb:fb": "Amazon Technologies",
    "74:e6:b8": "LG Electronics",
    "aa:bb:cc": "IoT Device"
  }
}
```

## Configuration Validation

### 1. Validate Configuration Files

```python
import json
import os

def validate_config():
    """Validate configuration files"""
    
    # Check main config
    if not os.path.exists('config.py'):
        print("Warning: config.py not found")
        return False
    
    # Check device config
    device_config = 'src/config/known_devices.json'
    if not os.path.exists(device_config):
        print("Warning: known_devices.json not found")
        return False
    
    try:
        with open(device_config, 'r') as f:
            data = json.load(f)
        
        # Validate structure
        required_sections = ['ip', 'mac', 'mac_prefix']
        for section in required_sections:
            if section not in data:
                print(f"Warning: Missing section '{section}' in device config")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in device config: {e}")
        return False

# Run validation
if validate_config():
    print("Configuration validation passed")
else:
    print("Configuration validation failed")
```

### 2. Test Configuration

```bash
# Test configuration loading
python -c "
from config import *
print(f'VERBOSE: {VERBOSE}')
print(f'DEBUG_MODE: {DEBUG_MODE}')
print(f'WEB_PORT: {WEB_PORT}')
"

# Test device configuration
python -c "
import json
with open('src/config/known_devices.json', 'r') as f:
    data = json.load(f)
print(f'IP mappings: {len(data.get(\"ip\", {}))}')
print(f'MAC mappings: {len(data.get(\"mac\", {}))}')
print(f'MAC prefixes: {len(data.get(\"mac_prefix\", {}))}')
"
```

## Best Practices

### 1. Configuration Management

- **Version Control**: Keep configuration files in version control
- **Backup**: Regularly backup configuration files
- **Documentation**: Document custom configurations
- **Testing**: Test configurations before deployment

### 2. Security Considerations

- **Access Control**: Restrict access to configuration files
- **Sensitive Data**: Don't store sensitive data in configuration
- **Validation**: Validate all configuration inputs
- **Encryption**: Consider encrypting sensitive configurations

### 3. Performance Optimization

- **Minimal Logging**: Use minimal logging in production
- **Efficient Updates**: Use appropriate update intervals
- **Resource Limits**: Set reasonable resource limits
- **Monitoring**: Monitor configuration impact on performance

### 4. Troubleshooting

- **Debug Mode**: Enable debug mode for troubleshooting
- **Log Analysis**: Analyze logs for configuration issues
- **Validation**: Use configuration validation tools
- **Rollback**: Keep backup configurations for rollback

## Migration and Updates

### 1. Configuration Migration

When updating NetSleuth, check for configuration changes:

```bash
# Backup current configuration
cp config.py config.py.backup
cp src/config/known_devices.json src/config/known_devices.json.backup

# Update NetSleuth
git pull origin main

# Compare configurations
diff config.py config.py.backup
diff src/config/known_devices.json src/config/known_devices.json.backup
```

### 2. Configuration Updates

Update configurations when adding new features:

```python
# Example: Adding new configuration option
# Old config.py
VERBOSE = False
DEBUG_MODE = False

# New config.py
VERBOSE = False
DEBUG_MODE = False
NEW_FEATURE = True  # New configuration option
```

## Support and Troubleshooting

### Common Configuration Issues

1. **Invalid JSON**: Check JSON syntax in device configuration
2. **Missing Files**: Ensure all configuration files exist
3. **Permission Errors**: Check file permissions
4. **Import Errors**: Verify Python path and imports

### Getting Help

1. **Documentation**: Review this configuration guide
2. **Examples**: Check configuration examples
3. **Validation**: Use configuration validation tools
4. **Community**: Ask for help in community forums 