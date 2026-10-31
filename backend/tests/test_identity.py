import pytest

from netsleuth.utils.classify import DEVICE_TYPES, classify, is_placeholder_name
from netsleuth.utils.mac import is_randomized, normalize_mac, vendor_for


@pytest.mark.parametrize("raw, expected", [
    ("D0-57-7E-00-00-02", "d0:57:7e:00:00:02"),
    ("d057.7e00.0002", "d0:57:7e:00:00:02"),
    ("d0577e000002", "d0:57:7e:00:00:02"),
    ("ff:ff:ff:ff:ff:ff", None),       # broadcast
    ("00:00:00:00:00:00", None),
    ("01:00:5e:00:00:fb", None),       # multicast
    ("10.0.0.8", None),
    ("", None),
    (None, None),
])
def test_normalize_mac(raw, expected):
    assert normalize_mac(raw) == expected


def test_randomized_mac_has_no_vendor():
    assert is_randomized("02:11:22:33:44:55")
    assert vendor_for("02:11:22:33:44:55") is None


def test_vendor_lookup_known_and_unknown():
    assert vendor_for("ac:bc:32:00:00:01") == "Apple, Inc."
    # scapy echoes unknown OUIs back as the MAC; that must not leak out as a vendor
    assert vendor_for("d0:57:7e:00:00:02") is None


@pytest.mark.parametrize("hostname, vendor, expected", [
    ("Sams-iPhone", "Apple, Inc.", "phone"),
    ("Den-ZenBook", None, "computer"),
    ("Living-Room-TV", "Samsung", "tv"),
    ("Watch", "Apple, Inc.", "iot"),
    (None, "Roku, Inc.", "tv"),
    (None, "Raspberry Pi Foundation", "computer"),
    (None, "Espressif Inc.", "iot"),
    (None, "Some Engineering Co", "unknown"),   # "ring" must not match inside words
    ("algorithm-box", None, "unknown"),          # nor "lg"
    (None, None, "unknown"),
])
def test_classify(hostname, vendor, expected):
    assert classify(hostname, vendor) == expected


def test_gateway_is_always_router():
    assert classify("Sams-iPhone", None, is_gateway=True) == "router"


def test_classify_only_returns_known_types():
    assert classify("xbox", None) in DEVICE_TYPES


@pytest.mark.parametrize("vendor, expected", [
    ("Shenzhen Intellirocks Tech. Co. Ltd.", "iot"),     # Govee, not Intel
    ("Intel Corporate", "computer"),
    ("Sichuan AI-Link Technology Co., Ltd.", "iot"),
])
def test_vendor_word_matching(vendor, expected):
    assert classify(None, vendor) == expected


@pytest.mark.parametrize("name", ["none", "None", " localhost ", "(none)", "*"])
def test_placeholder_names(name):
    assert is_placeholder_name(name)


def test_real_name_is_not_placeholder():
    assert not is_placeholder_name("YN00AB123456")
