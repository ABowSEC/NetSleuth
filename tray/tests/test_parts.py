import json

import pytest

from tray import netinfo
from tray.client import is_notable
from tray.config import TrayConfig
from tray.paths import run_dir
from tray.preflight import AlreadyRunning, SingleInstance
from tray.supervisor import exit_message


def test_config_defaults_and_round_trip():
    assert TrayConfig.load() == TrayConfig()
    TrayConfig(interface="Wi-Fi", port=5050, notifications=False).save()
    assert TrayConfig.load() == TrayConfig(interface="Wi-Fi", port=5050, notifications=False)


def test_config_ignores_bad_values():
    TrayConfig.path().write_text(json.dumps({"interface": 5, "port": 80, "notifications": "yes", "x": 1}))
    assert TrayConfig.load() == TrayConfig()
    TrayConfig.path().write_text("{broken")
    assert TrayConfig.load() == TrayConfig()


def test_default_interface_prefers_the_routed_one():
    candidates = [("Ethernet 2", "192.168.56.1"), ("Wi-Fi", "10.0.0.50")]
    assert netinfo.default_interface(candidates, "10.0.0.50") == "Wi-Fi"
    assert netinfo.default_interface(candidates, None) == "Ethernet 2"
    assert netinfo.default_interface([], "10.0.0.50") is None


def test_candidate_interfaces_have_ipv4():
    for name, ip in netinfo.candidate_interfaces():
        assert name and ip.count(".") == 3 and not ip.startswith(("127.", "169.254."))


@pytest.mark.parametrize("event, notable", [
    ({"kind": "new_device", "severity": "medium", "data": {}}, True),
    ({"kind": "new_device", "severity": "info", "data": {"baseline": True}}, False),
    ({"kind": "mac_conflict", "severity": "high"}, True),
    ({"kind": "alert", "severity": "high"}, True),
    ({"kind": "alert", "severity": "medium"}, False),
    ({"kind": "joined", "severity": "info"}, False),
])
def test_notable_events(event, notable):
    assert is_notable(event) is notable


def test_single_instance_lock():
    first = SingleInstance(run_dir())
    try:
        with pytest.raises(AlreadyRunning):
            SingleInstance(run_dir())
    finally:
        first.release()
    SingleInstance(run_dir()).release()


def test_exit_messages_cover_documented_codes():
    assert "Npcap" in exit_message(3, 5000)
    assert "5000" in exit_message(4, 5000)
    assert exit_message(1, 5000) is None
