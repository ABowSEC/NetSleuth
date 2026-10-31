"""Turn raw packets into facts about local devices.

``parse`` is a pure function: it never touches the store, so it can be tested
with hand-built packets. Rules:

- A device is a local MAC. Remote IPs are never devices; they appear only as
  ``Flow.address`` of the local device that contacted them.
- An IP is attached to a MAC only when the IP is inside the local network.
  (Remote traffic arrives with the router's MAC; attaching those IPs is what
  used to merge the internet into the router's record.)
- DNS is attributed only to *queries* sent by local hosts, never responses.
- mDNS/LLMNR are used for device names, not logged as DNS queries.
- Only connection-initiating TCP (SYN without ACK) counts as a flow, so a
  local server answering many clients doesn't look like a port scan.
- Identification clues come only from what a device says about itself: its
  DHCP request, its own mDNS announcements, its own SSDP messages.
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether

from ..utils.classify import is_placeholder_name
from ..utils.mac import normalize_mac

_MDNS_PORTS = (5353, 5355)   # mDNS, LLMNR
_DHCP_PORTS = (67, 68)
_SSDP_PORT = 1900
# mDNS TXT keys that describe the device itself (model, friendly name).
_TXT_KEYS = {"md", "fn", "am", "model", "ty", "usb_MDL", "rpMd"}
_MAX_CLUE = 120
_MULTICAST = ipaddress.ip_network("224.0.0.0/4")


@dataclass(frozen=True)
class Sighting:
    mac: str
    ip: str | None = None


@dataclass(frozen=True)
class Hostname:
    mac: str
    hostname: str


@dataclass(frozen=True)
class Query:
    mac: str
    domain: str


@dataclass(frozen=True)
class Flow:
    mac: str
    address: str
    port: int | None
    proto: str            # "tcp" | "udp"
    local: bool           # destination is on the LAN


@dataclass(frozen=True)
class Clue:
    """Something a device revealed about what it is (see utils/identify.py)."""
    mac: str
    source: str
    key: str
    value: str
    confidence: float = 1.0


Fact = Sighting | Hostname | Query | Flow | Clue


def _local_ip(value: str | None, network: IPv4Network) -> str | None:
    """Return ``value`` if it is a usable host address inside ``network``."""
    try:
        addr = IPv4Address(value)
    except (ValueError, TypeError):
        return None
    if addr not in network or addr in (network.network_address, network.broadcast_address):
        return None
    return str(addr)


def _text(value) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if not isinstance(value, str):
        return None
    value = value.strip().strip("\x00").rstrip(".")
    return value or None


def _hostname(value) -> str | None:
    """A device-reported name, minus placeholders like "none" or "localhost"."""
    name = _text(value)
    if not name or is_placeholder_name(name):
        return None
    return name


def _is_unicast_destination(address: str, network: IPv4Network) -> bool:
    addr = IPv4Address(address)
    return not (addr in _MULTICAST or addr.is_unspecified or address == "255.255.255.255"
                or addr == network.broadcast_address)


def parse(pkt, network: IPv4Network) -> list[Fact]:
    if not pkt.haslayer(Ether):
        return []
    facts: list[Fact] = []
    eth_mac = normalize_mac(pkt[Ether].src)

    if pkt.haslayer(ARP):
        arp = pkt[ARP]
        mac = normalize_mac(arp.hwsrc)
        if mac:
            # ARP probes (psrc 0.0.0.0) still prove the device is present.
            facts.append(Sighting(mac, _local_ip(arp.psrc, network)))
        return facts

    if pkt.haslayer(BOOTP) and pkt.haslayer(DHCP):
        facts.extend(_parse_dhcp(pkt, network))
        return facts

    if not eth_mac or not pkt.haslayer(IP):
        return facts

    ip = pkt[IP]
    src = _local_ip(ip.src, network)
    # Traffic from the internet arrives with the router's MAC: the router is
    # present, but the remote IP is not its address.
    facts.append(Sighting(eth_mac, src))
    if not src:
        return facts

    if pkt.haslayer(UDP):
        udp = pkt[UDP]
        if pkt.haslayer(DNS):
            if udp.sport in _MDNS_PORTS or udp.dport in _MDNS_PORTS:
                facts.extend(_parse_mdns(pkt[DNS], eth_mac, src))
                return facts
            if udp.dport == 53 and pkt[DNS].qr == 0:
                facts.extend(_parse_dns_query(pkt[DNS], eth_mac))
                return facts
        if _SSDP_PORT in (udp.sport, udp.dport):
            facts.extend(_parse_ssdp(bytes(udp.payload), eth_mac))
            return facts
        if udp.dport in _DHCP_PORTS or udp.sport == 53:
            return facts
        if _is_unicast_destination(ip.dst, network):
            facts.append(Flow(eth_mac, ip.dst, int(udp.dport), "udp", _local_ip(ip.dst, network) is not None))

    elif pkt.haslayer(TCP):
        tcp = pkt[TCP]
        if tcp.flags.S and not tcp.flags.A and _is_unicast_destination(ip.dst, network):
            facts.append(Flow(eth_mac, ip.dst, int(tcp.dport), "tcp", _local_ip(ip.dst, network) is not None))

    return facts


def _dhcp_options(pkt) -> dict:
    options = {}
    for opt in pkt[DHCP].options:
        if isinstance(opt, tuple) and len(opt) >= 2:
            options[opt[0]] = opt[1]
    return options


def _parse_dhcp(pkt, network: IPv4Network) -> list[Fact]:
    bootp = pkt[BOOTP]
    mac = normalize_mac(bytes(bootp.chaddr[:6]).hex())
    if not mac:
        return []
    options = _dhcp_options(pkt)
    facts: list[Fact] = []

    if bootp.op == 1:  # client -> server
        facts.append(Sighting(mac, _local_ip(bootp.ciaddr, network)))
        hostname = _hostname(options.get("hostname"))
        if hostname:
            facts.append(Hostname(mac, hostname))
        vendor_class = _text(options.get("vendor_class_id"))
        if vendor_class:
            facts.append(Clue(mac, "dhcp", "vendor_class", vendor_class[:_MAX_CLUE], 0.9))
        params = options.get("param_req_list")
        if isinstance(params, (list, tuple, bytes)) and params:
            facts.append(Clue(mac, "dhcp", "params", ",".join(str(int(x)) for x in params)[:_MAX_CLUE], 0.5))
    elif options.get("message-type") == 5:  # server ACK: address assigned to chaddr
        facts.append(Sighting(mac, _local_ip(bootp.yiaddr, network)))
    return facts


def _parse_dns_query(dns, mac: str) -> list[Fact]:
    qname = _text(dns.qd[0].qname) if dns.qd else None
    if not qname or qname.endswith((".local", ".arpa")):
        return []
    return [Query(mac, qname.lower())]


def _service_of(name: str) -> str | None:
    """'Living Room._googlecast._tcp.local' -> '_googlecast._tcp'."""
    labels = name.removesuffix(".local").split(".")
    for i in range(len(labels) - 1):
        if labels[i].startswith("_") and labels[i + 1] in ("_tcp", "_udp"):
            return f"{labels[i]}.{labels[i + 1]}"
    return None


def _parse_mdns(dns, mac: str, src_ip: str) -> list[Fact]:
    """What a device announces about itself over mDNS/LLMNR.

    - A records for the sender's own address give its hostname.
    - PTR records give the services it offers (and the instance name it uses).
    - TXT records carry model and friendly-name keys.
    """
    if dns.qr != 1:
        return []
    facts: list[Fact] = []
    named = False
    for rr in [*(dns.an or []), *(dns.ar or [])]:
        rtype = getattr(rr, "type", None)
        owner = _text(getattr(rr, "rrname", None)) or ""
        if rtype == 1 and not named and str(getattr(rr, "rdata", "")) == src_ip:
            name = _hostname(owner)
            if name:
                facts.append(Hostname(mac, name.removesuffix(".local")))
                named = True
        elif rtype == 12:
            target = _text(getattr(rr, "rdata", None)) or ""
            service = _service_of(target) or _service_of(owner)
            if service and not owner.startswith("_services._dns-sd"):
                facts.append(Clue(mac, "mdns", f"service:{service}", service, 0.9))
                instance = target.split("._")[0] if "._" in target else ""
                if instance and not instance.startswith("_"):
                    facts.append(Clue(mac, "mdns", f"instance:{service}", instance[:_MAX_CLUE], 0.6))
        elif rtype == 16:
            for entry in getattr(rr, "rdata", None) or []:
                text = _text(entry) or ""
                key, sep, value = text.partition("=")
                if sep and key in _TXT_KEYS and value.strip():
                    facts.append(Clue(mac, "mdns", f"txt:{key}", value.strip()[:_MAX_CLUE], 0.9))
    return facts


def _parse_ssdp(payload: bytes, mac: str) -> list[Fact]:
    """SSDP announcements (NOTIFY) and search replies sent by the device itself.

    LOCATION is only recorded: fetching the description it points to is
    active probing, which happens in Identify mode.
    """
    try:
        text = payload[:4096].decode("utf-8", errors="ignore")
    except Exception:
        return []
    first, _, rest = text.partition("\r\n")
    if not (first.startswith("NOTIFY * HTTP/1.") or first.startswith("HTTP/1.1 200")):
        return []
    headers = {}
    for line in rest.split("\r\n"):
        name, sep, value = line.partition(":")
        if sep:
            headers[name.strip().lower()] = value.strip()
    facts: list[Fact] = []
    if headers.get("server"):
        facts.append(Clue(mac, "ssdp", "server", headers["server"][:_MAX_CLUE], 0.6))
    location = headers.get("location", "")
    if location.lower().startswith("http://"):
        facts.append(Clue(mac, "ssdp", "location", location[:_MAX_CLUE], 0.5))
    return facts
