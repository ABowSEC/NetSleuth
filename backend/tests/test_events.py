from datetime import timedelta
from ipaddress import ip_network

import pytest

from netsleuth.core import events as ev
from netsleuth.core.events import EventEngine
from netsleuth.core.packets import Flow, Sighting
from netsleuth.core.pipeline import Pipeline
from netsleuth.core.store import DeviceStore
from netsleuth.timeutil import utcnow

NET = ip_network("10.0.0.0/24")
LAPTOP = "d0:57:7e:00:00:02"
PHONE = "02:11:22:33:44:55"
ROUTER = "f4:c1:14:00:00:01"
INTRUDER = "02:66:66:66:66:66"


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def store(tmp_path):
    s = DeviceStore(tmp_path / "devices.db")
    yield s
    s.close()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def engine(store, clock):
    return EventEngine(store, gateway_ip="10.0.0.1", clock=clock)


@pytest.fixture
def pipeline(store, engine):
    return Pipeline(store, NET, gateway_ip="10.0.0.1", observer=engine)


def kinds(store):
    return [(e["kind"], e["severity"]) for e in reversed(store.list_events())]


def after_grace(clock):
    clock.t += ev.STARTUP_GRACE_S + 1


def test_new_device_fires_once(pipeline, store):
    pipeline.apply([Sighting(PHONE, "10.0.0.6")])
    pipeline.apply([Sighting(PHONE, "10.0.0.6")])
    assert kinds(store) == [("new_device", "medium")]
    assert "10.0.0.6" in store.list_events()[0]["message"]


def test_known_device_is_not_announced_as_new(pipeline, store):
    store.import_known(LAPTOP, "Zenbook")
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5")])
    assert kinds(store) == []


def test_joined_suppressed_during_grace_then_reported(pipeline, engine, store, clock):
    store.import_known(LAPTOP, "Zenbook")   # exists, offline
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5")])
    assert kinds(store) == []

    engine.on_offline(store.expire(600, now=utcnow() + timedelta(hours=1)))
    after_grace(clock)
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5")])
    assert kinds(store) == [("left", "info"), ("joined", "info")]
    assert store.list_events()[0]["message"] == "Zenbook joined at 10.0.0.5"


def test_returning_device_reported_even_in_grace(pipeline, store):
    store.observe(LAPTOP, ts=utcnow() - timedelta(days=10))
    store.expire(timeout_s=600)
    store.update(LAPTOP, name="Zenbook", is_known=True)
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5")])
    event = store.list_events()[0]
    assert (event["kind"], event["severity"]) == ("joined", "low")
    assert event["data"]["days_away"] == 10


def test_ip_change(pipeline, store):
    pipeline.apply([Sighting(PHONE, "10.0.0.6")])
    pipeline.apply([Sighting(PHONE, "10.0.0.7")])
    assert kinds(store)[-1] == ("ip_changed", "info")


def test_ip_reuse_after_owner_left_is_not_a_conflict(pipeline, store):
    store.observe(LAPTOP, "10.0.0.5", ts=utcnow() - timedelta(hours=2))
    pipeline.apply([Sighting(PHONE, "10.0.0.5")])
    assert "mac_conflict" not in [k for k, _ in kinds(store)]


def test_active_ip_conflict(pipeline, store):
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5")])
    pipeline.apply([Sighting(PHONE, "10.0.0.5")])
    assert ("mac_conflict", "high") in kinds(store)


def test_gateway_takeover_is_critical_and_rate_limited(pipeline, store, clock):
    pipeline.apply([Sighting(ROUTER, "10.0.0.1")])
    pipeline.apply([Sighting(INTRUDER, "10.0.0.1")])
    pipeline.apply([Sighting(ROUTER, "10.0.0.1")])
    pipeline.apply([Sighting(INTRUDER, "10.0.0.1")])
    criticals = [e for e in store.list_events() if e["severity"] == "critical"]
    assert len(criticals) == 2   # one per claiming MAC, then cooldown
    assert {e["mac"] for e in criticals} == {INTRUDER, ROUTER}


def test_port_scan_detected(engine, store, clock):
    store.observe(LAPTOP, "10.0.0.5")
    store.observe(PHONE, "10.0.0.6")
    for port in range(1, ev.PORT_SCAN_THRESHOLD + 5):
        engine.on_flow(Flow(LAPTOP, "10.0.0.6", port, "tcp", True))
    alerts = [e for e in store.list_events() if e["kind"] == "alert"]
    assert len(alerts) == 1 and alerts[0]["data"]["rule"] == "port_scan"


def test_slow_ports_outside_window_are_not_a_scan(engine, store, clock):
    for port in range(1, ev.PORT_SCAN_THRESHOLD + 5):
        clock.t += ev.SCAN_WINDOW_S / 4
        engine.on_flow(Flow(LAPTOP, "10.0.0.6", port, "tcp", True))
    assert store.list_events() == []


def test_internet_flows_never_alert(engine, store):
    for port in range(1, 100):
        engine.on_flow(Flow(LAPTOP, "93.184.216.34", port, "tcp", False))
    assert store.list_events() == []


def test_host_sweep_detected(engine, store):
    for host in range(2, ev.HOST_SWEEP_THRESHOLD + 3):
        engine.on_flow(Flow(LAPTOP, f"10.0.0.{host}", 22, "tcp", True))
    alerts = [e for e in store.list_events() if e["kind"] == "alert"]
    assert len(alerts) == 1 and alerts[0]["data"]["rule"] == "host_sweep"


def test_subscribers_receive_events_and_can_unsubscribe(engine):
    received = []
    unsubscribe = engine.subscribe(received.append)
    engine.emit("alert", "low", "one")
    unsubscribe()
    engine.emit("alert", "low", "two")
    assert [e["message"] for e in received] == ["one"]
    assert received[0]["id"] > 0


def test_failing_subscriber_does_not_break_emit(engine, store):
    engine.subscribe(lambda e: 1 / 0)
    engine.emit("alert", "low", "still stored")
    assert store.list_events()[0]["message"] == "still stored"
