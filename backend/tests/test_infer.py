import pytest

from netsleuth.utils.classify import classify
from netsleuth.utils.identify import Evidence, infer


def ev(*items):
    return [Evidence(source, key, value) for source, key, value in items]


@pytest.mark.parametrize("hostname, vendor", [
    ("Sams-iPhone", "Apple, Inc."),
    (None, "Roku, Inc"),
    ("Den-ZenBook", None),
    (None, "Some Engineering Co"),
    (None, None),
])
def test_without_evidence_matches_classify(hostname, vendor):
    assert infer([], vendor, hostname).type == classify(hostname, vendor)


def test_upnp_description_names_a_roku():
    identity = infer(ev(("upnp", "manufacturer", "Roku"), ("upnp", "modelName", "Roku Ultra"),
                        ("upnp", "friendlyName", "Bedroom Roku")), "Roku, Inc", "YN00AB123456")
    assert (identity.type, identity.model, identity.suggested_name) == ("tv", "Roku Ultra", "Bedroom Roku")


def test_upnp_access_point_with_manufacturer_prefix():
    identity = infer(ev(("upnp", "manufacturer", "NETGEAR"), ("upnp", "modelName", "RBS50"),
                        ("upnp", "deviceType", "urn:schemas-upnp-org:device:WLANAccessPointDevice:1")),
                     "Netgear", None)
    assert (identity.type, identity.model) == ("router", "NETGEAR RBS50")


def test_cast_speaker_versus_cast_tv():
    speaker = infer(ev(("mdns", "service:_googlecast._tcp", "_googlecast._tcp"),
                       ("mdns", "txt:md", "Google Nest Mini")), "Google, Inc.", None)
    assert (speaker.type, speaker.model) == ("speaker", "Google Nest Mini")

    tv = infer(ev(("mdns", "service:_googlecast._tcp", "_googlecast._tcp"), ("mdns", "txt:md", "Chromecast"),
                  ("mdns", "txt:fn", "Living Room TV")), "Google, Inc.", None)
    assert (tv.type, tv.model, tv.suggested_name) == ("tv", "Chromecast", "Living Room TV")


@pytest.mark.parametrize("key, value, device_type, model, os_name", [
    ("txt:am", "AppleTV6,2", "tv", "Apple TV", "tvOS"),
    ("txt:model", "MacBookPro18,1", "computer", "MacBook Pro", "macOS"),
    ("txt:rpMd", "iPad13,1", "tablet", "iPad", "iPadOS"),
    ("txt:model", "AudioAccessory5,1", "speaker", "HomePod", None),
])
def test_apple_model_identifiers(key, value, device_type, model, os_name):
    identity = infer(ev(("mdns", key, value)), "Apple, Inc.", None)
    assert (identity.type, identity.model, identity.os) == (device_type, model, os_name)


def test_printer_from_mdns():
    identity = infer(ev(("mdns", "service:_ipp._tcp", "_ipp._tcp"), ("mdns", "txt:ty", "EPSON ET-2800 Series")),
                     "Seiko Epson Corporation", None)
    assert (identity.type, identity.model) == ("printer", "EPSON ET-2800 Series")


def test_dhcp_vendor_class_os():
    assert infer(ev(("dhcp", "vendor_class", "android-dhcp-14")), None, None).os == "Android 14"
    assert infer(ev(("dhcp", "vendor_class", "android-dhcp-14")), None, None).type == "phone"
    assert infer(ev(("dhcp", "vendor_class", "dhcpcd-9.4.1:Linux-6.1")), None, None).os == "Linux"
    assert infer(ev(("dhcp", "vendor_class", "udhcp 1.31.1")), None, None).os == "Embedded Linux"


def test_windows_pc_from_netbios_and_dhcp():
    identity = infer(ev(("dhcp", "vendor_class", "MSFT 5.0"), ("netbios", "name", "DESKTOP-4FJ2K9Q")),
                     "Micro-Star INTL CO., LTD.", None)
    assert (identity.type, identity.os, identity.suggested_name) == ("computer", "Windows", "DESKTOP-4FJ2K9Q")


@pytest.mark.parametrize("ports, device_type", [("62078", "phone"), ("9100,80", "printer"), ("554", "camera"),
                                                ("1400", "speaker"), ("8060,80", "tv")])
def test_port_fingerprints(ports, device_type):
    assert infer(ev(("ports", "open", ports)), None, None).type == device_type


def test_iphone_ports_give_ios_hint():
    assert infer(ev(("ports", "open", "62078")), None, None).os == "iOS or iPadOS"


def test_specific_evidence_beats_vendor_guess():
    # Amazon's vendor rule says "iot"; a Fire TV advertises a TV service.
    identity = infer(ev(("mdns", "service:_amzn-wplay._tcp", "_amzn-wplay._tcp")), "Amazon Technologies Inc.", None)
    assert identity.type == "tv"


def test_gateway_is_always_router():
    identity = infer(ev(("mdns", "service:_googlecast._tcp", "_googlecast._tcp")), None, None, is_gateway=True)
    assert identity.type == "router"


@pytest.mark.parametrize("source, value, expected", [
    ("rdns", "roku-ultra.lan", "roku-ultra"),
    ("rdns", "10-0-0-5.example-isp.net", None),
    ("netbios", "localhost", None),
    ("netbios", "02-00-00-00-00-17", None),
    ("upnp", "Mr. Roku", "Mr. Roku"),
])
def test_suggested_name_filters_junk(source, value, expected):
    key = "friendlyName" if source == "upnp" else "name"
    assert infer(ev((source, key, value)), None, None).suggested_name == expected


def test_model_is_suggested_when_no_name():
    assert infer(ev(("mdns", "txt:md", "Chromecast")), None, None).suggested_name == "Chromecast"


def test_suggestion_equal_to_hostname_is_dropped():
    assert infer(ev(("rdns", "name", "den-zenbook.lan")), None, "Den-ZenBook").suggested_name is None


# ── Patterns seen on a real home network (values invented) ───────────────

def test_amazon_spotify_and_matter_is_a_speaker():
    identity = infer(ev(("mdns", "service:_matter._tcp", "_matter._tcp"),
                        ("mdns", "service:_spotify-connect._tcp", "_spotify-connect._tcp"),
                        ("mdns", "instance:_spotify-connect._tcp", "SpotifyConnect")),
                     "Amazon Technologies Inc.", None)
    assert identity.type == "speaker"
    assert identity.suggested_name is None   # "SpotifyConnect" is not a name


def test_amazon_fire_tv_stays_a_tv():
    identity = infer(ev(("mdns", "service:_amzn-wplay._tcp", "_amzn-wplay._tcp"),
                        ("mdns", "service:_spotify-connect._tcp", "_spotify-connect._tcp")),
                     "Amazon Technologies Inc.", None)
    assert identity.type == "tv"


def test_hisense_server_string_names_a_tv():
    identity = infer(ev(("ssdp", "server", "Platform 1.0 His/1.0 UPnP/1.0 DLNADOC/1.50")),
                     "Sichuan AI-Link Technology Co., Ltd.", None)
    assert (identity.type, identity.model) == ("tv", "Hisense smart TV")


@pytest.mark.parametrize("hostname, os_name", [("iPhone", "iOS"), ("Sams-iPad", "iPadOS"),
                                               ("Den-MacBook", "macOS"), (None, "iOS or macOS")])
def test_apple_dhcp_fingerprint(hostname, os_name):
    params = ("dhcp", "params", "1,121,3,6,15,108,114,119,162,252")
    assert infer(ev(params), None, hostname).os == os_name


def test_android_fingerprint_is_not_mistaken_for_apple():
    assert infer(ev(("dhcp", "params", "1,3,6,15,26,28,51,58,59,43")), None, None).os is None


def test_airplay_instance_name_is_suggested_and_ids_are_not():
    identity = infer(ev(("mdns", "instance:_airplay._tcp", "Grandma"),
                        ("mdns", "instance:_spotify-connect._tcp", "11111111-2222-3333-4444-555555555555")),
                     "Roku, Inc", "YN00AB123456")
    assert identity.suggested_name == "Grandma"


def test_raop_instance_strips_the_mac_prefix():
    identity = infer(ev(("mdns", "instance:_raop._tcp", "0A1B2C3D4E5F@Kitchen Speaker")), None, None)
    assert identity.suggested_name == "Kitchen Speaker"


def test_quest_link_on_a_pc_is_not_a_headset():
    identity = infer(ev(("mdns", "service:_oculusal_sp._tcp", "_oculusal_sp._tcp"),
                        ("mdns", "instance:_oculusal_sp._tcp", "sam::DESKTOP-0000000")),
                     "Micro-Star INTL CO., LTD.", "DESKTOP-0000000")
    assert identity.type == "computer" and identity.suggested_name is None
