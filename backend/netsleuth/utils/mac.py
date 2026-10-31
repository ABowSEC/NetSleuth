"""MAC address normalisation and vendor lookup."""
from __future__ import annotations

import re

_HEX12 = re.compile(r"^[0-9a-f]{12}$")


def normalize_mac(value: str | None) -> str | None:
    """Return ``aa:bb:cc:dd:ee:ff`` for any common MAC spelling, else None.

    Broadcast, all-zero and multicast addresses are rejected: they never
    identify a single device.
    """
    if not value:
        return None
    digits = re.sub(r"[^0-9a-fA-F]", "", value).lower()
    if not _HEX12.match(digits):
        return None
    if digits in ("000000000000", "ffffffffffff"):
        return None
    if int(digits[:2], 16) & 0x01:  # group (multicast) bit
        return None
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2))


def is_randomized(mac: str) -> bool:
    """True for locally administered addresses (phones' private Wi-Fi MACs)."""
    return bool(int(mac[:2], 16) & 0x02)


def vendor_for(mac: str) -> str | None:
    """IEEE OUI vendor name, or None when unknown/randomized."""
    if is_randomized(mac):
        return None
    try:
        from scapy.config import conf
        vendor = conf.manufdb._get_manuf(mac)
    except Exception:
        return None
    # scapy echoes the MAC back when the OUI is unknown
    if not vendor or normalize_mac(vendor) == mac:
        return None
    return vendor
