"""Work out what a device is from the clues ("evidence") collected about it.

Evidence comes from passive listening (DHCP, mDNS, SSDP announcements) and from
Identify mode (UPnP descriptions, NetBIOS, reverse DNS, optional port check).
Each item is (source, key, value). This module turns a device's evidence into
a type, a model, an OS and a suggested name.

Type is decided by weighted votes so that strong, device-specific clues
(a UPnP device type, an mDNS service) beat weak, ambiguous ones (the maker of
the network chip). With no votes it falls back to ``classify`` on the
hostname and vendor, as before.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from .classify import is_placeholder_name, type_from_name, type_from_vendor


@dataclass(frozen=True)
class Evidence:
    source: str          # dhcp | mdns | ssdp | upnp | netbios | rdns | ports | roku
    key: str
    value: str
    confidence: float = 1.0
    first_seen: str = ""
    last_seen: str = ""


@dataclass(frozen=True)
class Identity:
    type: str
    model: str | None = None
    os: str | None = None
    suggested_name: str | None = None


# ── Lookup tables ────────────────────────────────────────────────────────────

# mDNS service -> (type, weight). A device usually advertises several.
_SERVICE_TYPES: dict[str, tuple[str, float]] = {
    "_googlecast._tcp": ("tv", 0.8),
    "_airplay._tcp": ("tv", 0.5),
    "_raop._tcp": ("speaker", 0.4),
    "_spotify-connect._tcp": ("speaker", 0.5),
    "_sonos._tcp": ("speaker", 0.9),
    "_hap._tcp": ("iot", 0.7),
    "_homekit._tcp": ("iot", 0.6),
    "_matter._tcp": ("iot", 0.6),
    "_ipp._tcp": ("printer", 0.9),
    "_ipps._tcp": ("printer", 0.9),
    "_printer._tcp": ("printer", 0.9),
    "_pdl-datastream._tcp": ("printer", 0.9),
    "_scanner._tcp": ("printer", 0.7),
    "_smb._tcp": ("computer", 0.5),
    "_rfb._tcp": ("computer", 0.5),
    "_ssh._tcp": ("computer", 0.3),
    "_companion-link._tcp": ("phone", 0.3),
    "_androidtvremote2._tcp": ("tv", 0.9),
    "_amzn-wplay._tcp": ("tv", 0.6),
}

# Open TCP port -> (type, weight), from the opt-in port check.
_PORT_TYPES: dict[int, tuple[str, float]] = {
    62078: ("phone", 0.7),     # Apple lockdownd: iPhone / iPad
    9100: ("printer", 0.8),
    631: ("printer", 0.6),
    554: ("camera", 0.6),
    8008: ("tv", 0.5),
    8009: ("tv", 0.6),
    8060: ("tv", 0.8),         # Roku External Control Protocol
    1400: ("speaker", 0.8),    # Sonos
    445: ("computer", 0.5),
    548: ("computer", 0.5),    # AFP
}

# UPnP deviceType URN fragment -> type
_UPNP_DEVICE_TYPES: list[tuple[str, str]] = [
    ("internetgatewaydevice", "router"),
    ("wlanaccesspointdevice", "router"),
    ("printer", "printer"),
    ("mediarenderer", "tv"),
    ("dial-multiscreen", "tv"),
    ("zoneplayer", "speaker"),
    ("mediaserver", "computer"),
]

# Apple model identifiers (mDNS am= / model= / rpMd=) -> (friendly model, type)
_APPLE_MODELS: list[tuple[str, str, str]] = [
    ("appletv", "Apple TV", "tv"),
    ("audioaccessory", "HomePod", "speaker"),
    ("macbookpro", "MacBook Pro", "computer"),
    ("macbookair", "MacBook Air", "computer"),
    ("macbook", "MacBook", "computer"),
    ("imac", "iMac", "computer"),
    ("macmini", "Mac mini", "computer"),
    ("mac", "Mac", "computer"),
    ("iphone", "iPhone", "phone"),
    ("ipad", "iPad", "tablet"),
    ("watch", "Apple Watch", "iot"),
]

_ANDROID = re.compile(r"android-dhcp-(\d+)", re.I)
_IP_LIKE = re.compile(r"^\d{1,3}([.-]\d{1,3}){3}")
_GENERIC_NAMES = {"localhost", "android", "iphone", "ipad", "unknown", "default", "dhcp", "wlan0", "eth0"}


def _clean_name(value: str | None) -> str | None:
    """A usable human name, or None for placeholders, IP-derived and MAC-like strings."""
    if not value:
        return None
    name = value.strip().removesuffix(".local").removesuffix(".")
    name = name.split(".")[0] if "." in name and " " not in name else name
    if (not name or len(name) > 63 or is_placeholder_name(name) or name.lower() in _GENERIC_NAMES
            or _IP_LIKE.match(name) or re.fullmatch(r"[0-9a-fA-F:\-]{12,17}", name)):
        return None
    return name


def _apple_model(identifier: str) -> tuple[str, str] | None:
    lowered = identifier.lower().replace(" ", "")
    for prefix, model, device_type in _APPLE_MODELS:
        if lowered.startswith(prefix):
            return model, device_type
    return None


def _os_from(ev: dict[tuple[str, str], Evidence]) -> str | None:
    vendor_class = ev.get(("dhcp", "vendor_class"))
    if vendor_class:
        v = vendor_class.value
        m = _ANDROID.search(v)
        if m:
            return f"Android {m.group(1)}"
        if v.upper().startswith("MSFT"):
            return "Windows"
        if "dhcpcd" in v.lower():
            return "Linux"
        if v.lower().startswith("udhcp"):
            return "Embedded Linux"
    for key in ("txt:model", "txt:am", "txt:rpMd"):
        item = ev.get(("mdns", key))
        if item:
            apple = _apple_model(item.value)
            if apple:
                return {"computer": "macOS", "phone": "iOS", "tablet": "iPadOS", "tv": "tvOS"}.get(apple[1])
    ports = _open_ports(ev)
    if 62078 in ports:
        return "iOS or iPadOS"
    if ("netbios", "name") in ev:
        return "Windows"
    return None


def _open_ports(ev: dict[tuple[str, str], Evidence]) -> set[int]:
    item = ev.get(("ports", "open"))
    if not item:
        return set()
    return {int(p) for p in item.value.split(",") if p.strip().isdigit()}


def infer(evidence: list[Evidence], vendor: str | None, hostname: str | None, is_gateway: bool = False) -> Identity:
    ev = {(e.source, e.key): e for e in evidence}
    get = lambda source, key: ev[(source, key)].value if (source, key) in ev else None  # noqa: E731

    votes: dict[str, float] = defaultdict(float)
    model: str | None = None

    # 1. UPnP description (fetched in Identify mode) and Roku ECP
    manufacturer = get("upnp", "manufacturer")
    upnp_model = get("upnp", "modelName") or get("roku", "model_name")
    if upnp_model:
        model = upnp_model if not manufacturer or manufacturer.split()[0].lower() in upnp_model.lower() \
            else f"{manufacturer.split(',')[0]} {upnp_model}"
    device_type_urn = (get("upnp", "deviceType") or "").lower()
    for fragment, device_type in _UPNP_DEVICE_TYPES:
        if fragment in device_type_urn:
            votes[device_type] += 0.9
            break
    if get("roku", "model_name") or (manufacturer or "").lower().startswith("roku"):
        votes["tv"] += 0.9

    # 2. mDNS services and TXT records
    for (source, key), item in ev.items():
        if source == "mdns" and key.startswith("service:"):
            hit = _SERVICE_TYPES.get(key.removeprefix("service:"))
            if hit:
                votes[hit[0]] += hit[1] * item.confidence
    for key in ("txt:am", "txt:model", "txt:rpMd"):
        identifier = get("mdns", key)
        apple = _apple_model(identifier) if identifier else None
        if apple:
            model = model or apple[0]
            votes[apple[1]] += 0.9
            break
    md = get("mdns", "txt:md")
    if md:
        model = model or md
        if re.search(r"nest (mini|audio|hub)|google home|speaker", md, re.I):
            votes["speaker"] += 0.9
    printer_model = get("mdns", "txt:ty") or get("mdns", "txt:usb_MDL")
    if printer_model:
        model = model or printer_model
        votes["printer"] += 0.9

    # 3. Opt-in port check
    for port in _open_ports(ev):
        hit = _PORT_TYPES.get(port)
        if hit:
            votes[hit[0]] += hit[1]

    # 4. OS hints and names
    os_name = _os_from(ev)
    if os_name and os_name.startswith("Android"):
        votes["phone"] += 0.3
    elif os_name == "Windows":
        votes["computer"] += 0.4

    names = [get("upnp", "friendlyName"), get("mdns", "txt:fn"), get("roku", "friendly_name"),
             get("netbios", "name"), get("rdns", "name")]
    hostname_type = type_from_name(hostname)
    if hostname_type:
        votes[hostname_type] += 0.7
    for name in names:
        name_type = type_from_name(name)
        if name_type:
            votes[name_type] += 0.4
    vendor_type = type_from_vendor(vendor)
    if vendor_type:
        votes[vendor_type] += 0.3

    if is_gateway:
        device_type = "router"
    elif votes:
        device_type = max(votes.items(), key=lambda kv: kv[1])[0]
    else:
        device_type = "unknown"
    if device_type == "phone" and model and model.lower().startswith("ipad"):
        device_type = "tablet"

    suggested = next((n for n in map(_clean_name, names) if n), None)
    if not suggested and model:
        suggested = model
    if suggested and hostname and suggested.lower() == hostname.lower():
        suggested = None  # nothing new to offer

    return Identity(type=device_type, model=model, os=os_name, suggested_name=suggested)
