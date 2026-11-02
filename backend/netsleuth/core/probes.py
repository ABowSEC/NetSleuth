"""Active identification probes, used only while Identify mode is running.

Every probe asks a question devices on a home network already answer for each
other (UPnP/SSDP, mDNS, NetBIOS, reverse DNS), except ``port_check`` and
``http_title``, which only run when the user has turned the port check on.

Rules for every probe: hard timeouts, capped reads, never follow redirects,
never contact anything outside the local subnet.
"""
from __future__ import annotations

import http.client
import ipaddress
import logging
import random
import re
import socket
import struct
import threading
import time
import xml.etree.ElementTree as ET
from ipaddress import IPv4Network
from urllib.parse import urlsplit

log = logging.getLogger(__name__)

SSDP_GROUP = ("239.255.255.250", 1900)
MDNS_GROUP = ("224.0.0.251", 5353)
DESCRIPTION_LIMIT = 64 * 1024
TITLE_LIMIT = 32 * 1024
CHECK_PORTS = (80, 443, 445, 548, 554, 631, 1400, 7000, 8008, 8009, 8060, 9100, 62078)
UPNP_FIELDS = ("friendlyName", "manufacturer", "modelName", "modelNumber", "deviceType")
SEARCH_TARGETS = ("ssdp:all", "upnp:rootdevice", "urn:dial-multiscreen-org:service:dial:1", "roku:ecp", "ssdp:all")

_TITLE = re.compile(rb"<title[^>]*>(.*?)</title>", re.I | re.S)


# ── SSDP / UPnP ──────────────────────────────────────────────────────────────

def _parse_headers(text: str) -> dict[str, str]:
    headers = {}
    for line in text.split("\r\n")[1:]:
        name, sep, value = line.partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    return headers


def ssdp_search(own_ip: str, wait: float = 3.0) -> dict[str, dict[str, str]]:
    """Multicast an M-SEARCH and collect replies: {device ip: headers}."""
    def request(search_target: str) -> bytes:
        return ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\n"
                f"MX: 2\r\nST: {search_target}\r\n\r\n").encode()

    replies: dict[str, dict[str, str]] = {}
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.bind((own_ip, 0))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(own_ip))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        # Many devices ignore ssdp:all and only answer a search for their own kind.
        for search_target in SEARCH_TARGETS:
            sock.sendto(request(search_target), SSDP_GROUP)
        deadline = time.monotonic() + wait
        while (remaining := deadline - time.monotonic()) > 0:
            sock.settimeout(remaining)
            try:
                data, (ip, _) = sock.recvfrom(4096)
            except (TimeoutError, socket.timeout):
                break
            except OSError:
                continue
            text = data.decode("utf-8", errors="ignore")
            if text.startswith("HTTP/1.1 200"):
                merged = replies.setdefault(ip, {})
                for key, value in _parse_headers(text).items():
                    merged.setdefault(key, value)
    return replies


def _local_url(url: str, network: IPv4Network) -> tuple[str, int, str] | None:
    """(host, port, path) if ``url`` is plain http to an address inside ``network``."""
    try:
        parts = urlsplit(url)
        if parts.scheme != "http" or not parts.hostname:
            return None
        if ipaddress.IPv4Address(parts.hostname) not in network:
            return None
        return parts.hostname, parts.port or 80, (parts.path or "/") + (f"?{parts.query}" if parts.query else "")
    except ValueError:
        return None


def _http_get(host: str, port: int, path: str, limit: int, timeout: float, strict: bool = True) -> bytes | None:
    """GET without redirects; None on error or non-200.

    ``strict``: a body over ``limit`` is refused. Otherwise it is cut at ``limit``.
    """
    conn = http.client.HTTPConnection(host, port, timeout=timeout)
    try:
        conn.request("GET", path, headers={"User-Agent": "NetSleuth/identify", "Connection": "close"})
        resp = conn.getresponse()
        if resp.status != 200:
            return None
        body = resp.read(limit + 1)
        if len(body) > limit:
            return None if strict else body[:limit]
        return body
    except (OSError, http.client.HTTPException):
        return None
    finally:
        conn.close()


def parse_description(xml: bytes) -> dict[str, str]:
    """Top-level device fields from a UPnP description document."""
    if b"<!DOCTYPE" in xml[:2048] or b"<!ENTITY" in xml:
        return {}  # descriptions never need DTDs; refuse anything that declares one
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return {}
    found: dict[str, str] = {}
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag in UPNP_FIELDS and tag not in found and element.text and element.text.strip():
            found[tag] = element.text.strip()[:120]
    return found


def fetch_description(url: str, network: IPv4Network, timeout: float = 3.0) -> dict[str, str]:
    target = _local_url(url, network)
    if not target:
        return {}
    body = _http_get(*target, limit=DESCRIPTION_LIMIT, timeout=timeout)
    return parse_description(body) if body else {}


# ── mDNS ─────────────────────────────────────────────────────────────────────

def _dns_query(name: str) -> bytes:
    qname = b"".join(bytes([len(label)]) + label.encode() for label in name.split(".")) + b"\x00"
    return struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0) + qname + struct.pack(">HH", 12, 1)  # PTR, IN


def mdns_query(own_ip: str, wait: float = 2.0) -> int:
    """Ask every device to list its services, then ask for each service type.

    Answers are multicast, so the passive parser records them from capture;
    here we only read enough of them to learn which service types exist.
    Returns the number of service types queried.
    """
    from scapy.layers.dns import DNS

    service_types: set[str] = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP) as sock:
        sock.bind((own_ip, 0))
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(own_ip))
        sock.sendto(_dns_query("_services._dns-sd._udp.local"), MDNS_GROUP)
        deadline = time.monotonic() + wait
        while (remaining := deadline - time.monotonic()) > 0:
            sock.settimeout(remaining)
            try:
                data, _ = sock.recvfrom(9000)
            except (TimeoutError, socket.timeout):
                break
            except OSError:
                continue
            try:
                for rr in DNS(data).an or []:
                    if getattr(rr, "type", None) == 12:
                        target = rr.rdata.decode() if isinstance(rr.rdata, bytes) else str(rr.rdata)
                        service_types.add(target.rstrip("."))
            except Exception:
                continue
        for service in sorted(service_types)[:40]:
            sock.sendto(_dns_query(service), MDNS_GROUP)
            time.sleep(0.05)
    return len(service_types)


# ── NetBIOS ──────────────────────────────────────────────────────────────────

# "*" padded to 16 bytes, first-level encoded (RFC 1002 4.1)
_NBSTAT_NAME = b"\x20" + b"CK" + b"A" * 30 + b"\x00"


def netbios_request(txid: int) -> bytes:
    return struct.pack(">HHHHHH", txid, 0, 1, 0, 0, 0) + _NBSTAT_NAME + struct.pack(">HH", 0x21, 1)


def parse_netbios_response(data: bytes, txid: int) -> str | None:
    """The machine's unique workstation name from a node-status response."""
    try:
        if struct.unpack(">H", data[:2])[0] != txid:
            return None
        offset = 12 + len(_NBSTAT_NAME) + 4 + 4 + 2  # header, name, type/class, ttl, rdlength
        count = data[offset]
        offset += 1
        for i in range(count):
            entry = data[offset + 18 * i: offset + 18 * (i + 1)]
            if len(entry) < 18:
                break
            name = entry[:15].decode("ascii", errors="ignore").strip()
            suffix, flags = entry[15], struct.unpack(">H", entry[16:18])[0]
            if suffix == 0x00 and not flags & 0x8000 and name:
                return name
    except (IndexError, struct.error):
        return None
    return None


def netbios_name(ip: str, timeout: float = 1.5) -> str | None:
    txid = random.randint(1, 0xFFFF)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        try:
            sock.sendto(netbios_request(txid), (ip, 137))
            data, _ = sock.recvfrom(2048)
        except OSError:
            return None
    return parse_netbios_response(data, txid)


# ── Reverse DNS ──────────────────────────────────────────────────────────────

def reverse_dns(ip: str, timeout: float = 2.0) -> str | None:
    """PTR name from the OS resolver (normally the router), with a hard timeout."""
    result: list[str] = []

    def lookup() -> None:
        try:
            result.append(socket.gethostbyaddr(ip)[0])
        except OSError:
            pass

    thread = threading.Thread(target=lookup, daemon=True)
    thread.start()
    thread.join(timeout)
    name = result[0] if result else None
    return name if name and name != ip else None


# ── Opt-in port check ────────────────────────────────────────────────────────

def port_check(ip: str, ports: tuple[int, ...] = CHECK_PORTS, timeout: float = 0.5) -> list[int]:
    """TCP connect to a fixed short list of telltale ports. Opt-in only."""
    open_ports = []
    for port in ports:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            if sock.connect_ex((ip, port)) == 0:
                open_ports.append(port)
    return open_ports


def http_title(ip: str, port: int, timeout: float = 2.0) -> str | None:
    body = _http_get(ip, port, "/", limit=TITLE_LIMIT, timeout=timeout, strict=False)
    match = _TITLE.search(body or b"")
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1).decode("utf-8", errors="ignore")).strip()
    return title[:120] or None
