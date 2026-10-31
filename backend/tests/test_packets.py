from ipaddress import ip_network

from scapy.layers.dhcp import BOOTP, DHCP
from scapy.layers.dns import DNS, DNSQR, DNSRR
from scapy.layers.inet import IP, TCP, UDP
from scapy.layers.l2 import ARP, Ether
from scapy.packet import Raw

from netsleuth.core.packets import Clue, Flow, Hostname, Query, Sighting, parse

NET = ip_network("10.0.0.0/24")
LAPTOP = "d0:57:7e:00:00:02"
PHONE = "02:11:22:33:44:55"
ROUTER = "f4:c1:14:00:00:01"
ROKU = "a8:b5:7c:00:00:03"


def wire(pkt):
    """Serialise and re-dissect, as a captured packet would be."""
    return Ether(bytes(pkt))


def eth(src=LAPTOP, dst=ROUTER):
    return Ether(src=src, dst=dst)


def test_no_ethernet_no_facts():
    assert parse(IP(src="10.0.0.5", dst="1.1.1.1") / TCP(flags="S"), NET) == []


def test_arp_reply_is_sighting():
    pkt = eth(PHONE, "ff:ff:ff:ff:ff:ff") / ARP(op=2, hwsrc=PHONE, psrc="10.0.0.6", pdst="10.0.0.5")
    assert parse(wire(pkt), NET) == [Sighting(PHONE, "10.0.0.6")]


def test_arp_probe_from_zero_address_has_no_ip():
    pkt = eth(PHONE, "ff:ff:ff:ff:ff:ff") / ARP(op=1, hwsrc=PHONE, psrc="0.0.0.0", pdst="10.0.0.6")
    assert parse(wire(pkt), NET) == [Sighting(PHONE, None)]


def test_remote_ip_never_attached_to_router_mac():
    # A DNS response from the ISP resolver: arrives with the router's MAC.
    pkt = (eth(ROUTER, LAPTOP) / IP(src="203.0.113.53", dst="10.0.0.5")
           / UDP(sport=53, dport=50000) / DNS(qr=1, qd=DNSQR(qname="example.com")))
    assert parse(wire(pkt), NET) == [Sighting(ROUTER, None)]


def test_dns_query_attributed_to_local_sender():
    pkt = (eth() / IP(src="10.0.0.5", dst="203.0.113.53")
           / UDP(sport=50000, dport=53) / DNS(qr=0, qd=DNSQR(qname="Example.COM.")))
    assert parse(wire(pkt), NET) == [Sighting(LAPTOP, "10.0.0.5"), Query(LAPTOP, "example.com")]


def test_dns_response_from_local_resolver_is_not_a_query():
    pkt = (eth(ROUTER, LAPTOP) / IP(src="10.0.0.1", dst="10.0.0.5")
           / UDP(sport=53, dport=50000) / DNS(qr=1, qd=DNSQR(qname="example.com")))
    assert parse(wire(pkt), NET) == [Sighting(ROUTER, "10.0.0.1")]


def test_local_and_reverse_lookups_are_not_logged():
    pkt = (eth() / IP(src="10.0.0.5", dst="10.0.0.1")
           / UDP(sport=50000, dport=53) / DNS(qr=0, qd=DNSQR(qname="5.0.0.10.in-addr.arpa")))
    assert Query not in {type(f) for f in parse(wire(pkt), NET)}


def test_mdns_answer_names_the_sender():
    pkt = (eth(PHONE, "01:00:5e:00:00:fb") / IP(src="10.0.0.6", dst="224.0.0.251")
           / UDP(sport=5353, dport=5353)
           / DNS(qr=1, an=DNSRR(rrname="Sams-iPhone.local.", type="A", rdata="10.0.0.6")))
    assert parse(wire(pkt), NET) == [Sighting(PHONE, "10.0.0.6"), Hostname(PHONE, "Sams-iPhone")]


def test_mdns_answer_for_another_host_is_ignored():
    pkt = (eth(PHONE, "01:00:5e:00:00:fb") / IP(src="10.0.0.6", dst="224.0.0.251")
           / UDP(sport=5353, dport=5353)
           / DNS(qr=1, an=DNSRR(rrname="printer.local.", type="A", rdata="10.0.0.9")))
    assert parse(wire(pkt), NET) == [Sighting(PHONE, "10.0.0.6")]


def test_dhcp_request_hostname_and_ack():
    request = (eth(PHONE, "ff:ff:ff:ff:ff:ff") / IP(src="0.0.0.0", dst="255.255.255.255")
               / UDP(sport=68, dport=67)
               / BOOTP(op=1, chaddr=bytes.fromhex("021122334455"))
               / DHCP(options=[("message-type", "request"), ("hostname", b"Sams-iPhone"), "end"]))
    assert parse(wire(request), NET) == [Sighting(PHONE, None), Hostname(PHONE, "Sams-iPhone")]

    ack = (eth(ROUTER, PHONE) / IP(src="10.0.0.1", dst="10.0.0.6") / UDP(sport=67, dport=68)
           / BOOTP(op=2, yiaddr="10.0.0.6", chaddr=bytes.fromhex("021122334455"))
           / DHCP(options=[("message-type", "ack"), "end"]))
    assert parse(wire(ack), NET) == [Sighting(PHONE, "10.0.0.6")]


def test_dhcp_non_string_hostname_is_ignored():
    pkt = (eth(PHONE, "ff:ff:ff:ff:ff:ff") / IP(src="0.0.0.0", dst="255.255.255.255")
           / UDP(sport=68, dport=67) / BOOTP(op=1, chaddr=bytes.fromhex("021122334455"))
           / DHCP(options=[("message-type", "request"), ("hostname", b"\x00\x00"), "end"]))
    assert parse(wire(pkt), NET) == [Sighting(PHONE, None)]


def test_tcp_syn_is_a_flow_but_syn_ack_is_not():
    syn = eth() / IP(src="10.0.0.5", dst="93.184.216.34") / TCP(sport=50000, dport=443, flags="S")
    assert parse(wire(syn), NET) == [Sighting(LAPTOP, "10.0.0.5"), Flow(LAPTOP, "93.184.216.34", 443, "tcp", False)]

    # A local server replying to a client must not look like it is scanning ports.
    syn_ack = eth() / IP(src="10.0.0.5", dst="10.0.0.6") / TCP(sport=8080, dport=50001, flags="SA")
    assert parse(wire(syn_ack), NET) == [Sighting(LAPTOP, "10.0.0.5")]


def test_udp_flow_skips_broadcast_and_multicast():
    flow = eth() / IP(src="10.0.0.5", dst="10.0.0.6") / UDP(sport=50000, dport=9999)
    assert parse(wire(flow), NET)[-1] == Flow(LAPTOP, "10.0.0.6", 9999, "udp", True)

    for dst in ("10.0.0.255", "255.255.255.255", "239.255.255.250"):
        pkt = eth() / IP(src="10.0.0.5", dst=dst) / UDP(sport=50000, dport=1900)
        assert parse(wire(pkt), NET) == [Sighting(LAPTOP, "10.0.0.5")]


def test_multicast_source_mac_is_ignored():
    pkt = Ether(src="01:00:5e:00:00:01", dst=LAPTOP) / IP(src="10.0.0.9", dst="10.0.0.5") / UDP()
    assert parse(wire(pkt), NET) == []


def test_dhcp_placeholder_hostname_is_ignored():
    pkt = (eth(PHONE, "ff:ff:ff:ff:ff:ff") / IP(src="0.0.0.0", dst="255.255.255.255")
           / UDP(sport=68, dport=67) / BOOTP(op=1, chaddr=bytes.fromhex("021122334455"))
           / DHCP(options=[("message-type", "request"), ("hostname", b"none"), "end"]))
    assert parse(wire(pkt), NET) == [Sighting(PHONE, None)]


# ── Identification clues ─────────────────────────────────────────────────

def clues(facts):
    return {(f.source, f.key): f.value for f in facts if isinstance(f, Clue)}


def test_dhcp_request_reveals_client_type_and_fingerprint():
    pkt = (eth(PHONE, "ff:ff:ff:ff:ff:ff") / IP(src="0.0.0.0", dst="255.255.255.255")
           / UDP(sport=68, dport=67) / BOOTP(op=1, chaddr=bytes.fromhex("021122334455"))
           / DHCP(options=[("message-type", "request"), ("vendor_class_id", b"android-dhcp-14"),
                           ("param_req_list", [1, 3, 6, 15, 26, 28, 51, 58, 59, 43]), "end"]))
    assert clues(parse(wire(pkt), NET)) == {
        ("dhcp", "vendor_class"): "android-dhcp-14",
        ("dhcp", "params"): "1,3,6,15,26,28,51,58,59,43",
    }


def test_mdns_announcement_reveals_services_and_txt():
    pkt = (eth(PHONE, "01:00:5e:00:00:fb") / IP(src="10.0.0.6", dst="224.0.0.251") / UDP(sport=5353, dport=5353)
           / DNS(qr=1,
                 an=[DNSRR(rrname="_googlecast._tcp.local.", type="PTR",
                           rdata="Living Room TV-abc123._googlecast._tcp.local."),
                     DNSRR(rrname="Living Room TV-abc123._googlecast._tcp.local.", type="TXT",
                           rdata=[b"md=Chromecast", b"fn=Living Room TV", b"id=ignored", b"ve=05"])],
                 ar=[DNSRR(rrname="abc123.local.", type="A", rdata="10.0.0.6")]))
    facts = parse(wire(pkt), NET)
    assert clues(facts) == {
        ("mdns", "service:_googlecast._tcp"): "_googlecast._tcp",
        ("mdns", "instance:_googlecast._tcp"): "Living Room TV-abc123",
        ("mdns", "txt:md"): "Chromecast",
        ("mdns", "txt:fn"): "Living Room TV",
    }
    assert Hostname(PHONE, "abc123") in facts


def test_mdns_service_enumeration_is_not_a_service():
    pkt = (eth(PHONE, "01:00:5e:00:00:fb") / IP(src="10.0.0.6", dst="224.0.0.251") / UDP(sport=5353, dport=5353)
           / DNS(qr=1, an=[DNSRR(rrname="_services._dns-sd._udp.local.", type="PTR", rdata="_airplay._tcp.local.")]))
    assert clues(parse(wire(pkt), NET)) == {}


def test_ssdp_notify_reveals_server_and_location():
    payload = (b"NOTIFY * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nLOCATION: http://10.0.0.30:8060/\r\n"
               b"SERVER: Roku/12.5.0 UPnP/1.0 Roku/12.5.0\r\nNT: roku:ecp\r\n\r\n")
    pkt = eth(ROKU) / IP(src="10.0.0.30", dst="239.255.255.250") / UDP(sport=1900, dport=1900) / Raw(payload)
    facts = parse(wire(pkt), NET)
    assert clues(facts) == {("ssdp", "server"): "Roku/12.5.0 UPnP/1.0 Roku/12.5.0",
                            ("ssdp", "location"): "http://10.0.0.30:8060/"}
    assert not any(isinstance(f, Flow) for f in facts)


def test_ssdp_search_request_is_ignored():
    payload = b'M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: "ssdp:discover"\r\nST: ssdp:all\r\n\r\n'
    pkt = eth() / IP(src="10.0.0.5", dst="239.255.255.250") / UDP(sport=50000, dport=1900) / Raw(payload)
    assert clues(parse(wire(pkt), NET)) == {}
