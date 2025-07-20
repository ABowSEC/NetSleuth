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

