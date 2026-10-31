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
"""
from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from ipaddress import IPv4Address, IPv4Network

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether

from ..utils.mac import normalize_mac

_MDNS_PORTS = (5353, 5355)   # mDNS, LLMNR
_DHCP_PORTS = (67, 68)
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


Fact = Sighting | Hostname | Query | Flow


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
        hostname = _text(options.get("hostname"))
        if hostname:
            facts.append(Hostname(mac, hostname))
    elif options.get("message-type") == 5:  # server ACK: address assigned to chaddr
        facts.append(Sighting(mac, _local_ip(bootp.yiaddr, network)))
    return facts


def _parse_dns_query(dns, mac: str) -> list[Fact]:
    qname = _text(dns.qd[0].qname) if dns.qd else None
    if not qname or qname.endswith((".local", ".arpa")):
        return []
    return [Query(mac, qname.lower())]


def _parse_mdns(dns, mac: str, src_ip: str) -> list[Fact]:
    """mDNS/LLMNR answers that map a name to the sender's own address."""
    if dns.qr != 1:
        return []
    for rr in dns.an or []:
        if getattr(rr, "type", None) == 1 and str(getattr(rr, "rdata", "")) == src_ip:
            name = _text(rr.rrname)
            if name:
                return [Hostname(mac, name.removesuffix(".local"))]
    return []
