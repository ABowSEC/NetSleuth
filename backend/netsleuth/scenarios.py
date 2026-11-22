"""Synthetic capture files for replay mode: ``python -m netsleuth.scenarios OUTDIR``.

Every MAC, IP and name here is invented. A real maker prefix is used only where
the scenario needs a vendor lookup (router, laptop). The LAN is 192.168.77.0/24
with the router at .1.

Each scenario starts with the same household (minute 0-1), so a first-run
replay reports it as one "first scan found N devices" summary. Anything that
happens after the 2-minute start-up grace (from 150 s) is reported on its own,
as it would be live.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS, DNSQR, DNSRR
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether
from scapy.packet import Raw

SUBNET = "192.168.77.0/24"
GATEWAY_IP = "192.168.77.1"
T0 = 1_790_000_000.0          # capture start (late 2026); only differences matter

ROUTER = "f4:c1:14:00:00:01"
LAPTOP = "d0:57:7e:00:00:02"
PHONE = "02:5a:00:00:00:03"
CAST = "02:5a:00:00:00:04"
STREAMER = "02:5a:00:00:00:05"
PRINTER = "02:5a:00:00:00:06"
INTRUDER = "02:66:00:00:00:66"

IPS = {
    ROUTER: GATEWAY_IP,
    LAPTOP: "192.168.77.20",
    PHONE: "192.168.77.21",
    CAST: "192.168.77.30",
    STREAMER: "192.168.77.31",
    PRINTER: "192.168.77.40",
    INTRUDER: "192.168.77.66",
}
HOUSEHOLD = (ROUTER, LAPTOP, PHONE, CAST, STREAMER, PRINTER)


@dataclass
class Scenario:
    name: str
    description: str
    packets: list = field(default_factory=list)
    # What a first-run replay should produce (checked by tests/test_replay.py).
    devices: set[str] = field(default_factory=set)
    alerts: set[str] = field(default_factory=set)        # alert rules, plus "gateway_conflict"
    new_devices: set[str] = field(default_factory=set)   # MACs announced after the grace period

    def add(self, t: float, pkt) -> None:
        pkt.time = T0 + t
        self.packets.append(pkt)


def _mac_bytes(mac: str) -> bytes:
    return bytes.fromhex(mac.replace(":", ""))


def arp_reply(mac: str, ip: str, to_mac: str = ROUTER):
    return Ether(src=mac, dst=to_mac) / ARP(op=2, hwsrc=mac, psrc=ip, hwdst=to_mac, pdst=GATEWAY_IP)


def dhcp_request(mac: str, hostname: str | None = None, vendor_class: str | None = None):
    options = [("message-type", "request"), ("requested_addr", IPS.get(mac, "0.0.0.0"))]
    if hostname:
        options.append(("hostname", hostname.encode()))
    if vendor_class:
        options.append(("vendor_class_id", vendor_class.encode()))
    options += [("param_req_list", [1, 3, 6, 15, 119, 252]), "end"]
    return (Ether(src=mac, dst="ff:ff:ff:ff:ff:ff") / IP(src="0.0.0.0", dst="255.255.255.255")
            / UDP(sport=68, dport=67) / BOOTP(op=1, chaddr=_mac_bytes(mac)) / DHCP(options=options))


def dhcp_ack(mac: str):
    return (Ether(src=ROUTER, dst=mac) / IP(src=GATEWAY_IP, dst=IPS[mac]) / UDP(sport=67, dport=68)
            / BOOTP(op=2, yiaddr=IPS[mac], chaddr=_mac_bytes(mac)) / DHCP(options=[("message-type", "ack"), "end"]))


def dns_query(mac: str, domain: str):
    return (Ether(src=mac, dst=ROUTER) / IP(src=IPS[mac], dst=GATEWAY_IP) / UDP(sport=53000, dport=53)
            / DNS(rd=1, qd=DNSQR(qname=domain)))


def syn(mac: str, dst_ip: str, port: int, dst_mac: str = ROUTER, sport: int = 50000):
    return Ether(src=mac, dst=dst_mac) / IP(src=IPS[mac], dst=dst_ip) / TCP(sport=sport, dport=port, flags="S")


def mdns_cast(mac: str, friendly: str, model: str):
    instance = f"{friendly.replace(' ', '-')}-a1b2._googlecast._tcp.local."
    return (Ether(src=mac, dst="01:00:5e:00:00:fb") / IP(src=IPS[mac], dst="224.0.0.251") / UDP(sport=5353, dport=5353)
            / DNS(qr=1, aa=1,
                  an=[DNSRR(rrname="_googlecast._tcp.local.", type="PTR", rdata=instance),
                      DNSRR(rrname=instance, type="TXT", rdata=[f"md={model}".encode(), f"fn={friendly}".encode()])],
                  ar=[DNSRR(rrname="cast-a1b2.local.", type="A", rdata=IPS[mac])]))


def ssdp_notify(mac: str, server: str, port: int):
    payload = (f"NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nLOCATION: http://{IPS[mac]}:{port}/\r\n"
               f"NT: upnp:rootdevice\r\nNTS: ssdp:alive\r\nSERVER: {server}\r\n\r\n").encode()
    return (Ether(src=mac, dst="01:00:5e:7f:ff:fa") / IP(src=IPS[mac], dst="239.255.255.250")
            / UDP(sport=1900, dport=1900) / Raw(payload))


def household(s: Scenario) -> None:
    """The normal home: everything shows up in the first minute."""
    s.add(0.0, arp_reply(ROUTER, GATEWAY_IP, to_mac=LAPTOP))
    s.add(1.0, dhcp_request(LAPTOP, hostname="study-laptop", vendor_class="MSFT 5.0"))
    s.add(1.1, dhcp_ack(LAPTOP))
    s.add(3.0, dhcp_request(PHONE, hostname="Pixel-Test", vendor_class="android-dhcp-14"))
    s.add(3.1, dhcp_ack(PHONE))
    s.add(5.0, mdns_cast(CAST, "Living Room TV", "Chromecast"))
    s.add(8.0, ssdp_notify(STREAMER, "Roku/9.4.0 UPnP/1.0 Roku/9.4.0", 8060))
    s.add(10.0, arp_reply(PRINTER, IPS[PRINTER]))
    for i, domain in enumerate(("example.com", "example.org", "example.net")):
        s.add(12.0 + i, dns_query(LAPTOP, domain))
        s.add(12.5 + i, dns_query(PHONE, domain))
    s.add(20.0, syn(LAPTOP, "203.0.113.10", 443))
    s.add(21.0, syn(PHONE, "203.0.113.10", 443, sport=50001))
    s.add(30.0, syn(LAPTOP, IPS[PRINTER], 631, dst_mac=PRINTER))
    s.add(60.0, arp_reply(ROUTER, GATEWAY_IP, to_mac=PHONE))
    s.devices.update(HOUSEHOLD)


def baseline() -> Scenario:
    s = Scenario("baseline", "A quiet household: one first-scan summary, no alerts.")
    household(s)
    s.add(130.0, dns_query(LAPTOP, "example.com"))   # past the grace period, so the summary is reported
    return s


def new_device() -> Scenario:
    s = Scenario("new_device", "A stranger joins after start-up and is announced on its own.")
    household(s)
    s.add(150.0, dhcp_request(INTRUDER, hostname="unknown-box"))
    s.add(150.1, dhcp_ack(INTRUDER))
    s.add(152.0, dns_query(INTRUDER, "example.com"))
    s.devices.add(INTRUDER)
    s.new_devices.add(INTRUDER)
    return s


def gateway_spoof() -> Scenario:
    s = Scenario("gateway_spoof", "Another device claims the router's IP (ARP spoofing).")
    household(s)
    s.add(150.0, arp_reply(INTRUDER, IPS[INTRUDER]))
    s.add(155.0, arp_reply(ROUTER, GATEWAY_IP, to_mac=LAPTOP))
    for i in range(5):
        s.add(160.0 + i * 2, arp_reply(INTRUDER, GATEWAY_IP, to_mac=LAPTOP))
    s.devices.add(INTRUDER)
    s.new_devices.add(INTRUDER)
    s.alerts.add("gateway_conflict")
    return s


def port_scan() -> Scenario:
    s = Scenario("port_scan", "One device opens 30 ports on the printer within 15 seconds.")
    household(s)
    s.add(150.0, arp_reply(INTRUDER, IPS[INTRUDER]))
    for i, port in enumerate(range(20, 50)):
        s.add(155.0 + i * 0.5, syn(INTRUDER, IPS[PRINTER], port, dst_mac=PRINTER, sport=40000 + i))
    s.devices.add(INTRUDER)
    s.new_devices.add(INTRUDER)
    s.alerts.add("port_scan")
    return s


def host_sweep() -> Scenario:
    s = Scenario("host_sweep", "One device tries port 445 on 30 addresses within 15 seconds.")
    household(s)
    s.add(150.0, arp_reply(INTRUDER, IPS[INTRUDER]))
    for i in range(30):
        s.add(155.0 + i * 0.5, syn(INTRUDER, f"192.168.77.{100 + i}", 445, sport=41000 + i))
    s.devices.add(INTRUDER)
    s.new_devices.add(INTRUDER)
    s.alerts.add("host_sweep")
    return s


SCENARIOS = {f.__name__: f for f in (baseline, new_device, gateway_spoof, port_scan, host_sweep)}


def write_all(outdir: Path) -> list[Path]:
    from scapy.utils import wrpcap

    outdir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, build in SCENARIOS.items():
        path = outdir / f"{name}.pcap"
        wrpcap(str(path), build().packets)
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: python -m netsleuth.scenarios OUTDIR", file=sys.stderr)
        return 2
    for path in write_all(Path(argv[0])):
        print(f"{path}  ({SCENARIOS[path.stem]().description})")
    print(f"Replay one with: python -m netsleuth --replay <file> --subnet {SUBNET} --gateway {GATEWAY_IP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
