import socket
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_network

import pytest

from netsleuth.core import probes

LOOPBACK = ip_network("127.0.0.0/8")

ROKU_XML = b"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <device>
    <deviceType>urn:roku-com:device:player:1-0</deviceType>
    <friendlyName>Bedroom Roku</friendlyName>
    <manufacturer>Roku</manufacturer>
    <modelName>Roku Ultra</modelName>
    <modelNumber>4800X</modelNumber>
    <deviceList><device><friendlyName>Embedded service</friendlyName></device></deviceList>
  </device>
</root>"""


# ── Description parsing ──────────────────────────────────────────────────

def test_parse_description_takes_top_level_device_fields():
    assert probes.parse_description(ROKU_XML) == {
        "deviceType": "urn:roku-com:device:player:1-0",
        "friendlyName": "Bedroom Roku",
        "manufacturer": "Roku",
        "modelName": "Roku Ultra",
        "modelNumber": "4800X",
    }


@pytest.mark.parametrize("xml", [
    b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaa">]><root><device><modelName>&a;</modelName></device></root>',
    b"<root><device><modelName>unclosed",
    b"not xml at all",
])
def test_parse_description_refuses_dtds_and_garbage(xml):
    assert probes.parse_description(xml) == {}


@pytest.mark.parametrize("url, ok", [
    ("http://127.0.0.1:8060/", True),
    ("http://127.0.0.1/desc.xml?x=1", True),
    ("https://127.0.0.1/", False),          # only plain http descriptions
    ("http://203.0.113.9/desc.xml", False),  # outside the local network
    ("http://roku.local/", False),          # names would need DNS: never followed
    ("ftp://127.0.0.1/", False),
])
def test_only_local_http_urls_are_fetched(url, ok):
    assert (probes._local_url(url, LOOPBACK) is not None) is ok


# ── HTTP fetches against a real local server ─────────────────────────────

class Handler(BaseHTTPRequestHandler):
    routes: dict[str, tuple[int, dict, bytes]] = {}

    def do_GET(self):
        status, headers, body = self.routes.get(self.path, (404, {}, b""))
        self.send_response(status)
        for k, v in headers.items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    Handler.routes = {}
    yield srv
    srv.shutdown()
    srv.server_close()


def url(server, path):
    return f"http://127.0.0.1:{server.server_address[1]}{path}"


def test_fetch_description(server):
    Handler.routes["/desc.xml"] = (200, {}, ROKU_XML)
    assert probes.fetch_description(url(server, "/desc.xml"), LOOPBACK)["modelName"] == "Roku Ultra"


def test_fetch_description_refuses_oversized_redirects_and_errors(server):
    Handler.routes["/big.xml"] = (200, {}, b"<root>" + b" " * probes.DESCRIPTION_LIMIT + b"</root>")
    Handler.routes["/moved"] = (302, {"Location": "http://203.0.113.9/evil.xml"}, b"")
    assert probes.fetch_description(url(server, "/big.xml"), LOOPBACK) == {}
    assert probes.fetch_description(url(server, "/moved"), LOOPBACK) == {}
    assert probes.fetch_description(url(server, "/missing"), LOOPBACK) == {}


def test_http_title_reads_only_the_start_of_big_pages(server):
    page = b"<html><head><title>  Printer\n Status </title></head>" + b"x" * (probes.TITLE_LIMIT * 2)
    Handler.routes["/"] = (200, {}, page)
    assert probes.http_title("127.0.0.1", server.server_address[1]) == "Printer Status"


def test_http_title_none_without_title(server):
    Handler.routes["/"] = (200, {}, b"<html>no title</html>")
    assert probes.http_title("127.0.0.1", server.server_address[1]) is None


# ── NetBIOS ──────────────────────────────────────────────────────────────

def nbstat_response(txid, names):
    body = struct.pack(">HHHHHH", txid, 0x8400, 0, 1, 0, 0) + probes._NBSTAT_NAME + struct.pack(">HHIH", 0x21, 1, 0, 0)
    body += bytes([len(names)])
    for name, suffix, flags in names:
        body += name.ljust(15).encode() + bytes([suffix]) + struct.pack(">H", flags)
    return body


def test_netbios_response_picks_unique_workstation_name():
    data = nbstat_response(7, [("WORKGROUP", 0x00, 0x8400), ("DESKTOP-4FJ2K9Q", 0x00, 0x0400),
                               ("DESKTOP-4FJ2K9Q", 0x20, 0x0400)])
    assert probes.parse_netbios_response(data, 7) == "DESKTOP-4FJ2K9Q"


def test_netbios_response_rejects_wrong_txid_and_truncation():
    data = nbstat_response(7, [("DESKTOP-4FJ2K9Q", 0x00, 0x0400)])
    assert probes.parse_netbios_response(data, 8) is None
    assert probes.parse_netbios_response(data[:30], 7) is None


def test_netbios_request_shape():
    req = probes.netbios_request(0x1234)
    assert len(req) == 50 and req[:2] == b"\x12\x34" and req[-4:] == b"\x00\x21\x00\x01"


# ── Port check and reverse DNS ───────────────────────────────────────────

def test_port_check_finds_listening_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        closed = port + 1 if port < 65535 else port - 1
        assert probes.port_check("127.0.0.1", ports=(port, closed), timeout=0.5) == [port]


def test_reverse_dns_gives_up_after_timeout(monkeypatch):
    monkeypatch.setattr(socket, "gethostbyaddr", lambda ip: time.sleep(5))
    started = time.monotonic()
    assert probes.reverse_dns("10.0.0.9", timeout=0.2) is None
    assert time.monotonic() - started < 1


def test_reverse_dns_ignores_echoed_ip(monkeypatch):
    monkeypatch.setattr(socket, "gethostbyaddr", lambda ip: (ip, [], [ip]))
    assert probes.reverse_dns("10.0.0.9") is None
    monkeypatch.setattr(socket, "gethostbyaddr", lambda ip: ("den-pc.lan", [], [ip]))
    assert probes.reverse_dns("10.0.0.9") == "den-pc.lan"
