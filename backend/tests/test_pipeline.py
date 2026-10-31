from datetime import timedelta
from ipaddress import ip_network

import pytest
from scapy.layers.inet import IP, TCP
from scapy.layers.l2 import Ether

from netsleuth.core.discovery import Discovery, sweep_target
from netsleuth.core.packets import Flow, Hostname, Query, Sighting
from netsleuth.core.pipeline import UDP_FLOW_WINDOW_S, Pipeline, PipelineObserver
from netsleuth.core.store import DeviceStore
from netsleuth.timeutil import utcnow

NET = ip_network("10.0.0.0/24")
LAPTOP = "d0:57:7e:00:00:02"
ROUTER = "f4:c1:14:00:00:01"


class Recorder(PipelineObserver):
    def __init__(self):
        self.sightings, self.offline, self.flows = [], [], []

    def on_sighting(self, mac, ip, obs):
        self.sightings.append((mac, ip, obs))

    def on_offline(self, devices):
        self.offline.extend(d.mac for d in devices)

    def on_flow(self, flow):
        self.flows.append(flow)


@pytest.fixture
def store(tmp_path):
    s = DeviceStore(tmp_path / "devices.db")
    yield s
    s.close()


@pytest.fixture
def recorder():
    return Recorder()


@pytest.fixture
def pipeline(store, recorder):
    return Pipeline(store, NET, gateway_ip="10.0.0.1", observer=recorder)


def test_facts_update_store(pipeline, store, recorder):
    pipeline.apply([
        Sighting(LAPTOP, "10.0.0.5"),
        Hostname(LAPTOP, "Den-ZenBook"),
        Query(LAPTOP, "example.com"),
        Flow(LAPTOP, "93.184.216.34", 443, "tcp", False),
    ])
    device = store.get(LAPTOP)
    assert device.hostname == "Den-ZenBook" and device.ips == ["10.0.0.5"]
    detail = store.detail(LAPTOP)
    assert detail["top_domains"][0]["domain"] == "example.com"
    assert detail["top_destinations"][0]["address"] == "93.184.216.34"
    assert recorder.sightings[0][2].is_new
    assert len(recorder.flows) == 1


def test_gateway_ip_marks_router(pipeline, store):
    pipeline.apply([Sighting(ROUTER, "10.0.0.1")])
    assert store.get(ROUTER).type == "router"


def test_udp_flows_deduplicated_within_window(pipeline, store, recorder):
    flow = Flow(LAPTOP, "10.0.0.6", 9999, "udp", True)
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5")])
    pipeline.apply([flow], now=0)
    pipeline.apply([flow], now=1)
    pipeline.apply([flow], now=UDP_FLOW_WINDOW_S + 1)
    assert len(recorder.flows) == 2
    assert store.detail(LAPTOP)["top_destinations"][0]["count"] == 2


def test_tcp_flows_are_not_deduplicated(pipeline, recorder):
    flow = Flow(LAPTOP, "1.1.1.1", 443, "tcp", False)
    pipeline.apply([Sighting(LAPTOP, "10.0.0.5"), flow, flow], now=0)
    assert len(recorder.flows) == 2


def test_housekeeping_reports_offline(pipeline, store, recorder):
    store.observe(LAPTOP, ts=utcnow() - timedelta(hours=1))
    pipeline.housekeeping()
    assert recorder.offline == [LAPTOP]


def test_paused_pipeline_drops_packets(pipeline):
    pipeline.pause()
    pipeline.submit(object())
    assert pipeline._queue.empty()
    pipeline.resume()
    pipeline.submit(object())
    assert pipeline._queue.qsize() == 1


def test_worker_processes_packets_and_survives_bad_ones(pipeline, store):
    pipeline.start()
    try:
        pipeline.submit("not a packet")  # parse() will raise on this
        pipeline.submit(Ether(src=LAPTOP, dst=ROUTER) / IP(src="10.0.0.5", dst="1.1.1.1") / TCP(flags="S"))
        import time
        deadline = time.time() + 2
        while store.get(LAPTOP) is None and time.time() < deadline:
            time.sleep(0.02)
        assert store.get(LAPTOP) is not None
    finally:
        pipeline.stop()


# ── Discovery ────────────────────────────────────────────────────────────

def test_sweep_target_caps_large_subnets():
    assert sweep_target(NET, "10.0.0.5") == NET
    assert sweep_target(ip_network("10.0.0.0/16"), "10.0.37.5") == ip_network("10.0.36.0/22")


def test_sweep_feeds_pipeline(pipeline, store):
    replies = [("D0-57-7E-00-00-02", "10.0.0.5"), ("ff:ff:ff:ff:ff:ff", "10.0.0.7")]
    discovery = Discovery(pipeline, "eth0", "10.0.0.2", lambda: 300, sweeper=lambda iface, net: replies)
    assert discovery.sweep_once() == 1
    assert store.get(LAPTOP).ips == ["10.0.0.5"]


def test_sweep_skipped_while_paused(pipeline):
    def fail(iface, net):
        raise AssertionError("swept while paused")

    discovery = Discovery(pipeline, "eth0", "10.0.0.2", lambda: 300, sweeper=fail)
    pipeline.pause()
    assert discovery.sweep_once() == 0
