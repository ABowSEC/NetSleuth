import socket
from ipaddress import ip_network

import pytest
from scapy.utils import wrpcap

from netsleuth import cli, scenarios
from netsleuth.core.events import EventEngine
from netsleuth.core.pipeline import Pipeline
from netsleuth.core.replay import ReplayClock, ReplayError, first_timestamp, infer_network, replay
from netsleuth.core.store import DeviceStore

NET = ip_network(scenarios.SUBNET)


def write(tmp_path, scenario):
    path = tmp_path / f"{scenario.name}.pcap"
    wrpcap(str(path), scenario.packets)
    return path


def run(tmp_path, scenario, **kwargs):
    path = write(tmp_path, scenario)
    clock = ReplayClock(first_timestamp(path))
    store = DeviceStore(tmp_path / "replay.db")
    engine = EventEngine(store, scenarios.GATEWAY_IP, clock=clock, first_run=True)
    pipeline = Pipeline(store, NET, scenarios.GATEWAY_IP, engine)
    count = replay(path, pipeline, clock=clock, **kwargs)
    return store, count


def alert_rules(store):
    rules = set()
    for event in store.list_events(limit=1000):
        if event["kind"] == "alert":
            rules.add(event["data"]["rule"])
        elif event["kind"] == "mac_conflict" and event["severity"] == "critical":
            rules.add("gateway_conflict")
    return rules


@pytest.mark.parametrize("name", list(scenarios.SCENARIOS))
def test_scenario_replays_as_expected(tmp_path, name):
    scenario = scenarios.SCENARIOS[name]()
    store, count = run(tmp_path, scenario)
    try:
        assert count == len(scenario.packets)
        assert {d.mac for d in store.list_devices()} == scenario.devices
        assert alert_rules(store) == scenario.alerts

        events = store.list_events(limit=1000)
        summaries = [e for e in events if e["kind"] == "new_device" and e["data"].get("baseline")]
        assert len(summaries) == 1
        assert summaries[0]["data"]["count"] == len(scenarios.HOUSEHOLD)
        announced = {e["mac"] for e in events if e["kind"] == "new_device" and not e["data"].get("baseline")}
        assert announced == scenario.new_devices
    finally:
        store.close()


def test_baseline_picks_up_names_and_clues(tmp_path):
    store, _ = run(tmp_path, scenarios.baseline())
    try:
        assert store.get(scenarios.LAPTOP).hostname == "study-laptop"
        assert store.get(scenarios.PHONE).ips[0] == scenarios.IPS[scenarios.PHONE]
        sources = {e.source for e in store.evidence(scenarios.CAST)}
        assert "mdns" in sources
        assert "ssdp" in {e.source for e in store.evidence(scenarios.STREAMER)}
        assert store.get(scenarios.ROUTER).is_gateway
    finally:
        store.close()


def test_infer_network(tmp_path):
    assert infer_network(write(tmp_path, scenarios.baseline())) == NET


def test_missing_file_is_a_replay_error(tmp_path):
    with pytest.raises(ReplayError):
        first_timestamp(tmp_path / "nope.pcap")


def test_not_a_capture_file_is_a_replay_error(tmp_path):
    bogus = tmp_path / "bogus.pcap"
    bogus.write_bytes(b"definitely not a pcap")
    with pytest.raises(ReplayError):
        infer_network(bogus)


def test_speed_keeps_pacing_and_caps_long_gaps(tmp_path):
    scenario = scenarios.Scenario("paced", "")
    scenario.add(0.0, scenarios.arp_reply(scenarios.ROUTER, scenarios.GATEWAY_IP))
    scenario.add(2.0, scenarios.arp_reply(scenarios.LAPTOP, scenarios.IPS[scenarios.LAPTOP]))
    scenario.add(100.0, scenarios.arp_reply(scenarios.PHONE, scenarios.IPS[scenarios.PHONE]))
    sleeps = []
    store, _ = run(tmp_path, scenario, speed=2.0, max_gap_s=5.0, sleep=sleeps.append)
    store.close()
    assert sleeps == pytest.approx([1.0, 2.5])


def test_paused_pipeline_skips_packets(tmp_path):
    path = write(tmp_path, scenarios.baseline())
    store = DeviceStore(tmp_path / "replay.db")
    pipeline = Pipeline(store, NET)
    pipeline.pause()
    try:
        assert replay(path, pipeline) == 0
        assert store.list_devices() == []
    finally:
        store.close()


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_cli_replay_uses_its_own_database(tmp_path, isolated_home):
    path = write(tmp_path, scenarios.port_scan())
    real_db = isolated_home / "devices.db"
    code = cli.main(["--replay", str(path), "--replay-exit", "--headless", "--port", str(free_port()),
                     "--gateway", scenarios.GATEWAY_IP])
    assert code == cli.EXIT_OK
    assert not real_db.exists()

    store = DeviceStore(cli.replay_db_path())
    try:
        assert {d.mac for d in store.list_devices()} == scenarios.port_scan().devices
        assert alert_rules(store) == {"port_scan"}
    finally:
        store.close()


def test_cli_replay_missing_file_is_usage_error(tmp_path):
    code = cli.main(["--replay", str(tmp_path / "nope.pcap"), "--replay-exit", "--headless",
                     "--port", str(free_port())])
    assert code == cli.EXIT_USAGE


def test_cli_replay_gateway_outside_subnet_is_usage_error(tmp_path):
    path = write(tmp_path, scenarios.baseline())
    code = cli.main(["--replay", str(path), "--replay-exit", "--headless", "--port", str(free_port()),
                     "--gateway", "10.9.9.1"])
    assert code == cli.EXIT_USAGE


def test_write_all(tmp_path):
    written = scenarios.write_all(tmp_path / "out")
    assert {p.stem for p in written} == set(scenarios.SCENARIOS)
