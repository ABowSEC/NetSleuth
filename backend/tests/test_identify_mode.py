import threading
import time
from datetime import timedelta
from ipaddress import ip_network

import pytest

from netsleuth.core.events import EventEngine
from netsleuth.core.identify_mode import AlreadyRunning, IdentifySession, MonitoringPaused, Probers
from netsleuth.core.packets import Flow
from netsleuth.core.store import DeviceStore
from netsleuth.timeutil import iso, utcnow

NET = ip_network("10.0.0.0/24")
ME = "02:00:00:00:00:99"         # this computer
ROUTER = "f4:c1:14:00:00:01"
ROKU = "a8:b5:7c:00:00:03"
PC = "02:00:00:00:00:10"

ROKU_DESC = {"manufacturer": "Roku", "modelName": "Roku Ultra", "friendlyName": "Bedroom Roku"}


class Fakes:
    """Network stand-ins that record what was asked."""

    def __init__(self, port_check=None):
        self.calls: list[tuple] = []
        self._port_check = port_check

    def probers(self, **overrides) -> Probers:
        def record(name, result):
            def fn(*args):
                self.calls.append((name, *args))
                return result(*args) if callable(result) else result
            return fn

        defaults = dict(
            ssdp_search=record("ssdp", {"10.0.0.30": {"location": "http://10.0.0.30:8060/", "server": "Roku/12.5"}}),
            fetch_description=record("desc", lambda url, net: ROKU_DESC if "10.0.0.30" in url else {}),
            mdns_query=record("mdns", 0),
            netbios_name=record("netbios", lambda ip: "DESKTOP-4FJ2K9Q" if ip == "10.0.0.10" else None),
            reverse_dns=record("rdns", None),
            port_check=record("ports", self._port_check or (lambda ip: [])),
            http_title=record("title", None),
        )
        return Probers(**{**defaults, **overrides})

    def hosts(self, probe):
        return sorted(args[0] for name, *args in self.calls if name == probe)


@pytest.fixture
def store(tmp_path):
    s = DeviceStore(tmp_path / "devices.db")
    for mac, ip in ((ME, "10.0.0.2"), (ROUTER, "10.0.0.1"), (ROKU, "10.0.0.30"), (PC, "10.0.0.10")):
        s.observe(mac, ip)
    s.mark_gateway(ROUTER)
    yield s
    s.close()


@pytest.fixture
def engine(store):
    return EventEngine(store, gateway_ip="10.0.0.1", own_mac=ME)


def session(store, engine, fakes, **kwargs):
    defaults = dict(network=NET, own_ip="10.0.0.2", own_mac=ME, gateway_ip="10.0.0.1",
                    probers=fakes.probers(), spacing=0)
    return IdentifySession(store, engine, **{**defaults, **kwargs})


def wait_idle(s, timeout=5.0):
    deadline = time.monotonic() + timeout
    while s.status()["running"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not s.status()["running"]


def last_event(store):
    return store.list_events(kind="identified", limit=1)[0]


def test_run_records_evidence_and_switches_itself_off(store, engine):
    fakes = Fakes()
    s = session(store, engine, fakes)
    status = s.start(minutes=10)
    assert status["running"] and status["total"] == 3    # router, Roku, PC; never this computer
    wait_idle(s)

    roku = store.get(ROKU)
    assert (roku.model, roku.suggested_name, roku.type) == ("Roku Ultra", "Bedroom Roku", "tv")
    assert store.get(PC).suggested_name == "DESKTOP-4FJ2K9Q"
    assert all(store.get(mac).last_identified for mac in (ROUTER, ROKU, PC))
    assert store.get(ME).last_identified is None

    event = last_event(store)
    assert event["message"].startswith("Identify finished: learned more about 2 of 3 devices (Roku Ultra")
    assert event["data"]["reason"] is None and event["data"]["checked"] == 3
    assert s.status() == {"running": False, "started_at": None, "ends_at": None, "done": 0, "total": 0,
                          "current": None, "port_check": False}


def test_port_check_only_runs_when_enabled_and_never_on_the_router(store, engine):
    fakes = Fakes()
    s = session(store, engine, fakes)
    s.start(minutes=10)
    wait_idle(s)
    assert fakes.hosts("ports") == []

    fakes = Fakes(port_check=lambda ip: [80, 9100] if ip == "10.0.0.10" else [])
    s = session(store, engine, fakes, port_check_enabled=lambda: True)
    assert s.start(minutes=10, macs=[ROUTER, ROKU, PC])["port_check"] is True
    wait_idle(s)
    assert fakes.hosts("ports") == ["10.0.0.10", "10.0.0.30"]
    assert {(e.source, e.key) for e in store.evidence(PC)} >= {("ports", "open")}
    assert fakes.hosts("title") == ["10.0.0.10"]


def test_recently_identified_devices_are_skipped_unless_named(store, engine):
    store.mark_identified(ROKU, ts=utcnow() - timedelta(days=1))
    store.mark_identified(PC, ts=utcnow() - timedelta(days=30))
    s = session(store, engine, Fakes())
    assert {mac for mac, _ in s.targets()} == {ROUTER, PC}
    assert {mac for mac, _ in s.targets([ROKU])} == {ROKU}


def test_offline_devices_are_not_probed(store, engine):
    store.expire(timeout_s=600, now=utcnow() + timedelta(hours=1))
    store.observe(ROKU, "10.0.0.30")
    assert {mac for mac, _ in session(store, engine, Fakes()).targets()} == {ROKU}


def test_nothing_to_check(store, engine):
    for mac in (ROUTER, ROKU, PC):
        store.mark_identified(mac)
    s = session(store, engine, Fakes())
    s.start(minutes=10)
    wait_idle(s)
    assert "nothing to check" in last_event(store)["message"]


def test_deadline_switches_it_off(store, engine):
    now = [0.0]
    fakes = Fakes()

    def slow_netbios(ip):
        now[0] += 400       # each host "takes" 400 s of a 10 min window
        return None

    s = session(store, engine, fakes, probers=fakes.probers(netbios_name=slow_netbios),
                clock=lambda: now[0], workers=1)
    s.start(minutes=10)
    wait_idle(s)
    event = last_event(store)
    assert event["data"]["reason"] == "time limit"
    assert event["data"]["checked"] < 3
    assert "reached its time limit" in event["message"]


def test_stop_ends_the_run(store, engine):
    release = threading.Event()
    fakes = Fakes()
    s = session(store, engine, fakes, probers=fakes.probers(netbios_name=lambda ip: release.wait(5) and None),
                workers=1, spacing=0.05)
    s.start(minutes=10)
    time.sleep(0.1)
    stopper = threading.Thread(target=s.stop)
    stopper.start()
    time.sleep(0.05)
    release.set()
    stopper.join(5)
    wait_idle(s)
    assert last_event(store)["data"]["reason"] == "stopped"


def test_pause_blocks_start_and_ends_a_running_pass(store, engine):
    paused = [True]
    fakes = Fakes()
    s = session(store, engine, fakes, is_paused=lambda: paused[0])
    with pytest.raises(MonitoringPaused):
        s.start(minutes=10)

    def pause_after_first(ip):
        paused[0] = True
        return None

    paused[0] = False
    s = session(store, engine, fakes, is_paused=lambda: paused[0],
                probers=fakes.probers(netbios_name=pause_after_first), workers=1)
    s.start(minutes=10)
    wait_idle(s)
    assert last_event(store)["data"]["reason"] == "paused"


def test_only_one_run_at_a_time(store, engine):
    release = threading.Event()
    fakes = Fakes()
    s = session(store, engine, fakes, probers=fakes.probers(ssdp_search=lambda ip: release.wait(5) and {}))
    s.start(minutes=10)
    with pytest.raises(AlreadyRunning):
        s.start(minutes=10)
    release.set()
    wait_idle(s)


def test_failing_probe_does_not_break_the_run(store, engine):
    def broken(ip):
        raise OSError("network unreachable")

    fakes = Fakes()
    s = session(store, engine, fakes, probers=fakes.probers(netbios_name=broken, ssdp_search=broken))
    s.start(minutes=10)
    wait_idle(s)
    assert last_event(store)["data"]["checked"] == 3


def test_subscribers_see_progress_and_the_end(store, engine):
    seen = []
    s = session(store, engine, Fakes())
    s.subscribe(seen.append)
    s.start(minutes=10)
    wait_idle(s)
    assert seen[0]["running"] is True
    assert max(st["done"] for st in seen) == 3
    assert seen[-1]["running"] is False


def test_own_traffic_never_alerts(store, engine):
    for port in range(1, 40):
        engine.on_flow(Flow(ME, "10.0.0.30", port, "tcp", True))
    for host in range(3, 40):
        engine.on_flow(Flow(ME, f"10.0.0.{host}", 445, "tcp", True))
    assert store.list_events(kind="alert") == []
