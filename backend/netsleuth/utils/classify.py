"""Best-effort device type from hostname and vendor.

Hostname rules win over vendor rules because hostnames are device-specific
("Sams-iPhone") while vendors are often ambiguous (Samsung makes phones and TVs).
Short tokens are matched as whole words so "lg" never matches "algorithm".
"""
from __future__ import annotations

import re

DEVICE_TYPES = (
    "router", "computer", "phone", "tablet", "tv", "speaker",
    "camera", "printer", "console", "iot", "unknown",
)

# (type, pattern) — first match wins. Patterns are applied to lowercase text.
_HOSTNAME_RULES: list[tuple[str, str]] = [
    ("phone", r"iphone|android|galaxy|pixel|\bphone\b|oneplus|moto"),
    ("tablet", r"ipad|\btab\b|galaxy-?tab|kindle|fire-?hd"),
    ("tv", r"\btv\b|roku|bravia|vizio|firetv|fire-?stick|chromecast|appletv|apple-tv|shield"),
    ("speaker", r"sonos|homepod|\becho\b|google-?home|nest-?(audio|mini)"),
    ("camera", r"\bcam\b|camera|ring-|wyze|arlo|doorbell|reolink"),
    ("printer", r"printer|officejet|laserjet|deskjet|epson|brother|canon"),
    ("console", r"xbox|playstation|\bps[45]\b|nintendo"),
    ("computer", r"macbook|imac|mac-?mini|desktop|laptop|\bpc\b|zenbook|thinkpad|surface|ubuntu|raspberrypi"),
    ("iot", r"esp[-_]?[0-9a-f]{4,}|tasmota|shelly|tuya|ecobee|nest|\bhue\b|wemo|kasa|plug|bulb|thermostat|watch"),
]

_VENDOR_RULES: list[tuple[str, str]] = [
    ("router", r"ubiquiti|eero|arris|technicolor|sagemcom|commscope|vantiva|netgear|mikrotik"),
    ("tv", r"roku|vizio|hisense|tcl"),
    ("speaker", r"sonos|bose"),
    ("camera", r"\bring\b|wyze|arlo|hikvision|dahua|reolink"),
    ("printer", r"seiko epson|brother industries|canon"),
    ("console", r"nintendo|sony interactive"),
    ("computer", r"intel|dell|lenovo|asustek|micro-star|gigabyte|raspberry pi|microsoft"),
    ("iot", r"espressif|tuya|shelly|ecobee|nest labs|signify|philips lighting|amazon technologies|belkin|tp-link"),
]


def _match(rules: list[tuple[str, str]], text: str | None) -> str | None:
    if not text:
        return None
    text = text.lower()
    for device_type, pattern in rules:
        if re.search(pattern, text):
            return device_type
    return None


def classify(hostname: str | None, vendor: str | None, is_gateway: bool = False) -> str:
    if is_gateway:
        return "router"
    return _match(_HOSTNAME_RULES, hostname) or _match(_VENDOR_RULES, vendor) or "unknown"
