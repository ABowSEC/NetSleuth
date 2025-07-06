# device_mapper.py
import json, os, re

CFG = os.path.join(os.path.dirname(__file__), "..", "config", "known_devices.json")
with open(CFG, "r") as f:
    _data = json.load(f)

_ip_lookup       = {k.lower(): v for k, v in _data.get("ip", {}).items()}
_mac_lookup      = {k.lower(): v for k, v in _data.get("mac", {}).items()}
_mac_prefix_lkp  = {k.lower(): v for k, v in _data.get("mac_prefix", {}).items()}

def normal(mac):
    """Normalize 74:e6:b8:d5:dd:36  OR 74-E6-B8-D5-DD-36 → 74:e6:b8:d5:dd:36"""
    mac = mac.lower()
    return re.sub(r"[^0-9a-f]", ":", mac)

def get_hostname(ip=None, mac=None):
    if ip and ip.lower() in _ip_lookup:
        return _ip_lookup[ip.lower()]
    if mac:
        mac = normal(mac)
        if mac in _mac_lookup:
            return _mac_lookup[mac]
        prefix = ":".join(mac.split(":")[:3])
        return _mac_prefix_lkp.get(prefix, "UNKNOWN DEVICE")
    return "UNKNOWN DEVICE"
