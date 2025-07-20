NetSleuth
A lightweight Python tool that passively monitors your local network. It shows active devices, their DNS queries, connections, and ARP activity. Without sending packets

## Features

- Passive network sniffing (no probing)
- DNS and ARP logging
- Device activity summaries every 30 seconds
- Basic device name mapping via JSON
- Windows and Linux/macOS support


## Usage

### Basic monitoring
```bash
python main.py
```

### With web interface
```bash
python main.py --web
```

### Specify interface and port
```bash
python main.py --web --interface "Wi-Fi" --port 8080
```

## Configuration

Edit `config.py` to control debugging and verbosity:
- `VERBOSE = True` - Shows detailed packet information
- `DEBUG_MODE = True` - Enables additional diagnostic output

## Device Identification

NetSleuth automatically identifies devices using:
1. **Known devices** - Configured in `src/config/known_devices.json`
2. **MAC address prefixes** - Manufacturer identification
3. **Behavioral analysis** - Device type detection based on DNS queries and connections
4. **IP-based identification** - Router, DNS server, etc.