# Installation Guide

This guide covers installing NetSleuth on different operating systems and troubleshooting common installation issues.

## Prerequisites

### System Requirements
- **Python 3.7+** (3.8+ recommended)
- **Network interface** with packet capture support
- **Administrator/root privileges** (for packet capture)

### Python Dependencies
- `scapy` - Packet capture and manipulation
- `psutil` - System and process utilities
- `rich` - Console formatting
- `flask` - Web interface framework

## Installation Methods

### Method 1: Direct Installation

1. **Clone the repository**
  

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation**
   ```bash
   python main.py --help
   ```

### Method 2: Virtual Environment (Recommended)

1. **Create virtual environment**
   ```bash
   python -m venv myVenv
   
   # Windows
   myVenv\Scripts\activate
   
   # Linux/macOS
   source myVenv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run NetSleuth**
   ```bash
   python main.py --web
   ```

## Platform-Specific Installation

### Windows

#### Prerequisites
- **Npcap** - Required for packet capture
- **Administrator privileges** - For packet capture access

#### Installation Steps

1. **Install Npcap**
   ```bash
   # Download from https://npcap.com/
   # Or use winget
   winget install nmap.npcap
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run as Administrator**
   ```bash
   # Right-click Command Prompt/PowerShell and "Run as Administrator"
   python main.py --web
   ```

#### Troubleshooting Windows Issues

**Permission Denied Errors**
```bash
# Run PowerShell as Administrator
Set-ExecutionPolicy RemoteSigned
```

**Npcap Not Found**
```bash
# Verify Npcap installation
sc query npcap
```

**Interface Not Found**
```bash
# List available interfaces
python -c "from src.utils.network_utils import get_active_interfaces; print(get_active_interfaces())"
```

### Linux

#### Prerequisites
- **libpcap-dev** - Packet capture library
- **root privileges** - For packet capture

#### Installation Steps

1. **Install system dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3-pip python3-venv libpcap-dev
   
   # CentOS/RHEL
   sudo yum install python3-pip libpcap-devel
   
   # Fedora
   sudo dnf install python3-pip libpcap-devel
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run with sudo**
   ```bash
   sudo python main.py --web
   ```

#### Troubleshooting Linux Issues

**Permission Denied**
```bash
# Grant packet capture capabilities
sudo setcap cap_net_raw=eip $(which python3)
```

**Interface Not Found**
```bash
# List network interfaces
ip link show
```

### macOS

#### Prerequisites
- **Xcode Command Line Tools** - For compilation
- **libpcap** - Packet capture library

#### Installation Steps

1. **Install system dependencies**
   ```bash
   # Install Xcode Command Line Tools
   xcode-select --install
   
   # Install libpcap via Homebrew
   brew install libpcap
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run with sudo**
   ```bash
   sudo python main.py --web
   ```

#### Troubleshooting macOS Issues

**Permission Denied**
```bash
# Grant full disk access to Terminal
# System Preferences > Security & Privacy > Privacy > Full Disk Access
```

**Interface Not Found**
```bash
# List network interfaces
ifconfig
```

## Docker Installation

### Using Docker

1. **Build the image**
   ```bash
   docker build -t netsleuth .
   ```

2. **Run the container**
   ```bash
   docker run --network host --privileged netsleuth python main.py --web
   ```

### Using Docker Compose

1. **Create docker-compose.yml**
   ```yaml
   version: '3.8'
   services:
     netsleuth:
       build: .
       network_mode: host
       privileged: true
       command: python main.py --web
   ```

2. **Run with Docker Compose**
   ```bash
   docker-compose up
   ```

## Verification

### Test Installation

1. **Check dependencies**
   ```bash
   python -c "import scapy, psutil, rich, flask; print('All dependencies installed!')"
   ```

2. **Test packet capture**
   ```bash
   python main.py --interface "lo"  # Test on loopback
   ```

3. **Test web interface**
   ```bash
   python main.py --web --port 5001
   # Open http://localhost:5001 in browser
   ```

### Common Verification Commands

```bash
# Check Python version
python --version

# Check installed packages
pip list

# Test network interface detection
python -c "from src.utils.network_utils import get_active_interfaces; print(get_active_interfaces())"

# Test device mapper
python -c "from src.utils.device_mapper import get_hostname; print(get_hostname('192.168.1.1'))"
```

## Troubleshooting

### General Issues

**Import Errors**
```bash
# Reinstall dependencies
pip uninstall -r requirements.txt
pip install -r requirements.txt
```

**Permission Errors**
```bash
# Windows: Run as Administrator
# Linux/macOS: Use sudo
sudo python main.py --web
```

**Network Interface Issues**
```bash
# List available interfaces
python -c "from src.utils.network_utils import get_active_interfaces; print(get_active_interfaces())"
```

### Performance Issues

**High CPU Usage**
- Reduce packet capture rate
- Use IP-only capture mode
- Filter specific protocols

**Memory Issues**
- Monitor device log size
- Restart application periodically
- Use debug mode to identify bottlenecks

### Security Considerations

**Firewall Configuration**
- Allow packet capture on monitoring interface
- Configure web interface firewall rules
- Restrict access to web dashboard

**Network Access**
- Only monitor your own network
- Don't capture sensitive traffic
- Use HTTPS for web interface in production

## Next Steps

After successful installation:

1. **Configure known devices** - Edit `src/config/known_devices.json`
2. **Set up monitoring** - Choose appropriate network interface
3. **Access web dashboard** - Open browser to configured port
4. **Review documentation** - Read other documentation files

## Support

If you encounter installation issues:

1. **Check troubleshooting section** above
2. **Review system requirements** and prerequisites
3. **Enable debug mode** for detailed error messages
4. **Check GitHub issues** for known problems
5. **Create new issue** with detailed error information 