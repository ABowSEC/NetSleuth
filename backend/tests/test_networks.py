import json
from ipaddress import ip_network

import pytest

from netsleuth import cli
from netsleuth.core import networks as net_mod
from netsleuth.core.discovery import Discovery
from netsleuth.core.events import EventEngine
from netsleuth.core.networks import (Fingerprint, NetworkRegistry, NetworkWatch, parse_arp_cache,
                                     parse_wlan_interfaces)
from netsleuth.core.pipeline import Pipeline
from netsleuth.core.store import DeviceStore
from netsleuth.settings import Settings
from netsleuth.web.api import AppContext, create_app

HOME_ROUTER = "f4:c1:14:00:00:01"
OTHER_ROUTER = "02:aa:00:00:00:01"
LAPTOP_NIC = "02:bb:00:00:00:02"
PHONE = "02:11:22:33:44:55"
JSON = {"Content-Type": "application/json"}

HOME = Fingerprint("10.0.0.0/24", "10.0.0.5", "10.0.0.1", HOME_ROUTER, "TestHome", "02:cc:00:00:00:01")
SCHOOL = Fingerprint("172.16.0.0/16", "172.16.4.9", "172.16.0.1", OTHER_ROUTER, "Campus")


@pytest.fixture
def registry(tmp_path):
    return NetworkRegistry(tmp_path)


# ── Fingerprints ─────────────────────────────────────────────────────────────

def test_id_is_router_and_subnet_not_name():
    renamed = Fingerprint(HOME.subnet, "10.0.0.77", HOME.gateway_ip, HOME_ROUTER, "Renamed")
    assert renamed.id == HOME.id
    assert Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, OTHER_ROUTER, "TestHome").id != HOME.id


def test_same_network():
    assert HOME.same_network(HOME)
    no_mac_yet = Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, None)
    assert HOME.same_network(no_mac_yet)
    assert not HOME.same_network(SCHOOL)
    assert not HOME.same_network(Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, OTHER_ROUTER))
    assert not HOME.same_network(Fingerprint(HOME.subnet, "10.0.0.6", HOME.gateway_ip, HOME_ROUTER))


def test_parse_arp_cache_windows_and_linux():
    windows = ("\r\nInterface: 10.0.0.5 --- 0x7\r\n  Internet Address      Physical Address      Type\r\n"
               "  10.0.0.1              f4-c1-14-00-00-01     dynamic\r\n"
               "  10.0.0.12             02-11-22-33-44-55     dynamic\r\n")
    assert parse_arp_cache(windows, "10.0.0.1") == HOME_ROUTER
    assert parse_arp_cache(windows, "10.0.0.9") is None
    linux = "10.0.0.1 dev wlan0 lladdr f4:c1:14:00:00:01 REACHABLE\n"
    assert parse_arp_cache(linux, "10.0.0.1") == HOME_ROUTER
    assert parse_arp_cache("10.0.0.1 dev wlan0 FAILED\n", "10.0.0.1") is None


NETSH = """
There are 2 interfaces on the system:

    Name                   : Wi-Fi
    Description            : Test Wireless Adapter
    Physical address       : 02:bb:00:00:00:02
    State                  : connected
    SSID                   : TestHome
    AP BSSID               : 02:cc:00:00:00:01
    Signal                 : 90%

    Name                   : Wi-Fi 2
    Description            : Test USB Adapter
    Physical address       : 02:bb:00:00:00:09
    State                  : connected
    SSID                   : Neighbour
    BSSID                  : 02:dd:00:00:00:01
"""


def test_parse_wlan_interfaces_picks_the_adapter_by_mac():
    assert parse_wlan_interfaces(NETSH, LAPTOP_NIC) == ("TestHome", "02:cc:00:00:00:01")
    assert parse_wlan_interfaces(NETSH, "02:bb:00:00:00:09") == ("Neighbour", "02:dd:00:00:00:01")
    assert parse_wlan_interfaces(NETSH, None) == (None, None)        # ambiguous


def test_parse_wlan_interfaces_without_location_permission():
    denied = "Network shell commands need location permission to access WLAN information.\n"
    assert parse_wlan_interfaces(denied, LAPTOP_NIC) == (None, None)
    assert parse_wlan_interfaces("", LAPTOP_NIC) == (None, None)


# ── Registry ─────────────────────────────────────────────────────────────────

def test_new_network_starts_idle_and_is_remembered(registry, tmp_path):
    network, created = registry.resolve(HOME)
    assert created and network.trust == "idle" and network.ssid == "TestHome"
    again, created = NetworkRegistry(tmp_path).resolve(HOME)
    assert not created and again.id == network.id


def test_networks_get_separate_databases(registry):
    home, _ = registry.resolve(HOME)
    school, _ = registry.resolve(SCHOOL)
    assert registry.db_path(home.id) != registry.db_path(school.id)
    assert registry.db_path(home.id).parent.is_dir()


def test_lookalike_network_is_flagged(registry):
    home, _ = registry.resolve(HOME)
    registry.update(home.id, trust="home")
    twin = Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, OTHER_ROUTER, "TestHome")
    network, created = registry.resolve(twin)
    assert created and network.trust == "idle" and network.similar_to == home.id


def test_network_first_seen_without_router_mac_is_upgraded(registry):
    early, _ = registry.resolve(Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, None, "TestHome"))
    later, created = registry.resolve(HOME)
    assert not created and later.id == early.id and later.gateway_macs == [HOME_ROUTER]


def test_update_validates_and_notifies(registry):
    network, _ = registry.resolve(HOME)
    seen = []
    registry.subscribe(seen.append)
    updated = registry.update(network.id, label="  Flat  ", trust="observe")
    assert (updated.label, updated.trust) == ("Flat", "observe")
    assert seen[-1].trust == "observe"
    with pytest.raises(ValueError):
        registry.update(network.id, trust="trusted")
    with pytest.raises(ValueError):
        registry.update(network.id, label="x" * 65)
    assert registry.update("nope", label="x") is None


def test_forget_deletes_the_folder(registry):
    school, _ = registry.resolve(SCHOOL)
    folder = registry.db_path(school.id).parent
    assert registry.forget(school.id)
    assert not folder.exists() and registry.get(school.id) is None
    assert not registry.forget(school.id)


def test_corrupt_index_is_moved_aside(tmp_path):
    (tmp_path / "networks.json").write_text("{not json", encoding="utf-8")
    assert NetworkRegistry(tmp_path).list() == []
    assert (tmp_path / "networks.json.bad").exists()


# ── Adopting the pre-profiles database ───────────────────────────────────────

def make_legacy(path, gateways=(), ips=()):
    """Routers are recorded a day apart, in the order given."""
    from datetime import timedelta

    from netsleuth.timeutil import utcnow

    start = utcnow() - timedelta(days=30)
    store = DeviceStore(path)
    for day, (mac, ip) in enumerate(gateways):
        store.observe(mac, ip, ts=start + timedelta(days=day))
        store.mark_gateway(mac)
    for mac, ip in ips:
        store.observe(mac, ip)
    store.flush()
    store.close()


REPLACEMENT_ROUTER = "02:aa:00:00:00:77"


def test_legacy_is_offered_with_a_hint_but_never_moved_by_itself(registry, tmp_path):
    legacy = tmp_path / "devices.db"
    make_legacy(legacy, gateways=[(HOME_ROUTER, "10.0.0.1"), (OTHER_ROUTER, "172.16.0.1")],
                ips=[(PHONE, "10.0.0.12")])
    school, _ = registry.resolve(SCHOOL)
    info = registry.legacy_info(school.id, legacy)
    assert info["available"] and info["adoptable"] and not info["likely_here"]
    assert info["devices"] == 3 and info["last_seen"]
    home, _ = registry.resolve(HOME)
    assert registry.legacy_info(home.id, legacy)["likely_here"]
    assert legacy.exists()                                     # nothing moved without a request


def test_lookalike_router_at_the_same_address_is_not_likely_here(registry, tmp_path):
    # Home router first; later a friend's router at the same address on the same subnet.
    legacy = tmp_path / "devices.db"
    make_legacy(legacy, gateways=[(HOME_ROUTER, "10.0.0.1"), (REPLACEMENT_ROUTER, "10.0.0.1")])
    friends, _ = registry.resolve(Fingerprint(HOME.subnet, HOME.own_ip, "10.0.0.1", REPLACEMENT_ROUTER, "AT&T"))
    assert not registry.legacy_info(friends.id, legacy)["likely_here"]


def test_legacy_without_router_is_likely_here_by_subnet(registry, tmp_path):
    legacy = tmp_path / "devices.db"
    make_legacy(legacy, ips=[(PHONE, "10.0.0.12"), (LAPTOP_NIC, "10.0.0.13")])
    school, _ = registry.resolve(SCHOOL)
    home, _ = registry.resolve(HOME)
    assert not registry.legacy_info(school.id, legacy)["likely_here"]
    assert registry.legacy_info(home.id, legacy)["likely_here"]


def test_requested_adoption_happens_once_with_the_chosen_trust(registry, tmp_path):
    legacy = tmp_path / "devices.db"
    make_legacy(legacy, gateways=[(HOME_ROUTER, "10.0.0.1")], ips=[(PHONE, "10.0.0.12")])
    home, _ = registry.resolve(HOME)
    assert registry.take_pending_adoption(home.id) is None
    registry.request_adoption(home.id, "observe")
    reloaded = NetworkRegistry(tmp_path)                       # survives the restart
    assert reloaded.take_pending_adoption(home.id) == "observe"
    assert reloaded.take_pending_adoption(home.id) is None
    assert reloaded.adopt_legacy(home.id, legacy, trust="observe")
    assert not legacy.exists() and reloaded.get(home.id).trust == "observe"
    store = DeviceStore(reloaded.db_path(home.id))
    try:
        assert store.get(PHONE) is not None
    finally:
        store.close()
    assert not reloaded.adopt_legacy(home.id, legacy)          # only once
    assert not reloaded.legacy_info(home.id, legacy)["available"]


def test_pending_adoption_for_another_network_is_dropped(registry):
    home, _ = registry.resolve(HOME)
    school, _ = registry.resolve(SCHOOL)
    registry.request_adoption(home.id, "home")
    assert registry.take_pending_adoption(school.id) is None
    assert registry.take_pending_adoption(home.id) is None


def test_adoption_replaces_an_empty_inventory_but_not_a_used_one(registry, tmp_path):
    legacy = tmp_path / "devices.db"
    make_legacy(legacy, gateways=[(HOME_ROUTER, "10.0.0.1")], ips=[(PHONE, "10.0.0.12")])
    home, _ = registry.resolve(HOME)
    DeviceStore(registry.db_path(home.id)).close()             # an idle start left it empty
    assert registry.legacy_info(home.id, legacy)["adoptable"]
    assert registry.adopt_legacy(home.id, legacy)

    other = NetworkRegistry(tmp_path / "second")
    legacy2 = tmp_path / "legacy2.db"
    make_legacy(legacy2, gateways=[(HOME_ROUTER, "10.0.0.1")])
    home2, _ = other.resolve(HOME)
    used = DeviceStore(other.db_path(home2.id))
    used.observe(PHONE, "10.0.0.12")
    used.flush()
    used.close()
    assert not other.legacy_info(home2.id, legacy2)["adoptable"]
    assert not other.adopt_legacy(home2.id, legacy2)
    assert legacy2.exists()


# ── Watching for network changes ─────────────────────────────────────────────

def test_watch_reports_link_loss_and_network_change():
    readings = iter([HOME, None, Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, None), SCHOOL])
    links, changes = [], []
    watch = NetworkWatch("Wi-Fi", HOME, on_change=changes.append, on_link=links.append,
                         read=lambda iface: next(readings))
    assert [watch.check() for _ in range(4)] == [False, False, False, True]
    assert links == [True, False, True, True]
    assert changes == [SCHOOL]


def test_identify_network_waits_for_the_router_mac(monkeypatch):
    readings = iter([Fingerprint(HOME.subnet, HOME.own_ip, HOME.gateway_ip, None), HOME])
    monkeypatch.setattr(net_mod, "current_fingerprint", lambda iface: next(readings))
    monkeypatch.setattr(cli.time, "sleep", lambda s: None)

    class Info:
        name, ip, network = "Wi-Fi", HOME.own_ip, ip_network(HOME.subnet)

    assert cli.identify_network(Info()) == HOME


# ── Trust gates ──────────────────────────────────────────────────────────────

def test_pipeline_drops_packets_while_not_accepting(tmp_path):
    store = DeviceStore(tmp_path / "d.db")
    accepting = {"on": False}
    pipeline = Pipeline(store, ip_network(HOME.subnet), accept=lambda: accepting["on"])
    try:
        pipeline.submit(object())
        assert pipeline._queue.qsize() == 0
        accepting["on"] = True
        pipeline.submit(object())
        assert pipeline._queue.qsize() == 1
    finally:
        store.close()


def test_sweep_only_where_allowed(tmp_path):
    store = DeviceStore(tmp_path / "d.db")
    pipeline = Pipeline(store, ip_network(HOME.subnet))

    def fail(iface, net):
        raise AssertionError("swept on a network that isn't Home")

    try:
        assert Discovery(pipeline, "eth0", HOME.own_ip, lambda: 300, sweeper=fail,
                         enabled=lambda: False).sweep_once() == 0
    finally:
        store.close()


def test_engine_begin_reopens_first_run_grace(tmp_path):
    store = DeviceStore(tmp_path / "d.db")
    now = {"t": 0.0}
    engine = EventEngine(store, clock=lambda: now["t"], first_run=True)
    try:
        now["t"] = 10_000.0          # idle for a long time, then switched on
        assert not engine.in_grace
        engine.begin()
        assert engine.in_grace and engine.first_run
    finally:
        store.close()


# ── API ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def api(tmp_path):
    registry = NetworkRegistry(tmp_path)
    home, _ = registry.resolve(HOME)
    school, _ = registry.resolve(SCHOOL)
    store = DeviceStore(tmp_path / "d.db")
    engine = EventEngine(store)
    pipeline = Pipeline(store, ip_network(HOME.subnet), observer=engine)
    legacy = tmp_path / "legacy.db"
    make_legacy(legacy, gateways=[(HOME_ROUTER, "10.0.0.1")], ips=[(PHONE, "10.0.0.12")])
    restarts = []
    ctx = AppContext(store=store, engine=engine, settings=Settings(), pipeline=pipeline,
                     interface="Wi-Fi", save_settings=False, networks=registry, network_id=home.id,
                     legacy_db=legacy, request_restart=lambda: restarts.append(1))
    ctx.restarts = restarts
    yield create_app(ctx).test_client(), ctx, home, school
    store.close()


def send(client, method, path, data=None):
    return client.open(path, method=method, data=json.dumps(data or {}), headers=JSON)


def test_health_reports_network_and_idle_is_not_capturing(api):
    client, _, home, _ = api
    body = client.get("/api/v1/health").get_json()
    assert body["network"] == {"id": home.id, "label": None, "ssid": "TestHome", "trust": "idle"}
    assert body["capturing"] is False
    send(client, "PATCH", "/api/v1/network", {"trust": "home"})
    assert client.get("/api/v1/health").get_json()["capturing"] is True


def test_get_and_patch_current_network(api):
    client, _, home, _ = api
    network = client.get("/api/v1/network").get_json()
    assert network["id"] == home.id and network["current"] is True
    assert network["gateway_mac"] == HOME_ROUTER
    patched = send(client, "PATCH", "/api/v1/network", {"label": "Flat", "trust": "observe"}).get_json()
    assert (patched["label"], patched["trust"]) == ("Flat", "observe")
    assert send(client, "PATCH", "/api/v1/network", {"trust": "yes"}).status_code == 400
    assert send(client, "PATCH", "/api/v1/network", {"colour": "red"}).status_code == 400


def test_list_patch_and_forget_networks(api):
    client, _, home, school = api
    listed = client.get("/api/v1/networks").get_json()
    assert {n["id"]: n["current"] for n in listed} == {home.id: True, school.id: False}
    assert send(client, "PATCH", f"/api/v1/networks/{school.id}", {"label": "School"}).get_json()["label"] == "School"
    assert send(client, "DELETE", f"/api/v1/networks/{home.id}").status_code == 409
    assert send(client, "DELETE", f"/api/v1/networks/{school.id}").status_code == 204
    assert send(client, "DELETE", f"/api/v1/networks/{school.id}").status_code == 404
    assert send(client, "PATCH", "/api/v1/networks/nope", {"label": "x"}).status_code == 404


def test_identify_refused_unless_home(api):
    client, _, _, _ = api
    response = send(client, "POST", "/api/v1/identify/start")
    assert response.status_code == 423 and response.get_json()["error"] == "network_not_home"


def test_legacy_offer_and_adoption_request(api):
    client, ctx, home, _ = api
    info = client.get("/api/v1/network/legacy").get_json()
    assert info == {**info, "available": True, "devices": 2, "likely_here": True, "adoptable": True}
    assert send(client, "POST", "/api/v1/network/legacy/adopt", {"trust": "idle"}).status_code == 400
    response = send(client, "POST", "/api/v1/network/legacy/adopt", {"trust": "observe"})
    assert response.status_code == 202 and response.get_json() == {"restarting": True}
    assert ctx.restarts == [1]
    assert ctx.networks.take_pending_adoption(home.id) == "observe"


def test_legacy_adoption_refused_when_this_network_has_records(api):
    client, ctx, home, _ = api
    used = DeviceStore(ctx.networks.db_path(home.id))
    used.observe(PHONE, "10.0.0.12")
    used.flush()
    used.close()
    response = send(client, "POST", "/api/v1/network/legacy/adopt")
    assert response.status_code == 409 and response.get_json()["error"] == "network_has_data"
    assert ctx.restarts == []


def test_no_profiles_in_replay_mode(tmp_path):
    store = DeviceStore(tmp_path / "d.db")
    ctx = AppContext(store=store, engine=EventEngine(store), settings=Settings(), save_settings=False)
    client = create_app(ctx).test_client()
    try:
        assert client.get("/api/v1/network").status_code == 404
        assert client.get("/api/v1/networks").get_json() == []
        assert client.get("/api/v1/health").get_json()["network"] is None
        assert client.get("/api/v1/network/legacy").status_code == 404
    finally:
        store.close()


# ── Reset ────────────────────────────────────────────────────────────────────

def test_reset_deletes_device_data_but_keeps_settings_and_logs(tmp_path):
    from netsleuth.core.networks import apply_pending_reset, request_reset

    registry = NetworkRegistry(tmp_path)
    home, _ = registry.resolve(HOME)
    make_legacy(registry.db_path(home.id), ips=[(PHONE, "10.0.0.12")])
    make_legacy(tmp_path / "devices.db", ips=[(PHONE, "10.0.0.12")])
    (tmp_path / "replay").mkdir()
    (tmp_path / "config.toml").write_text("retention_days = 7\n")
    (tmp_path / "tray.json").write_text("{}")
    (tmp_path / "logs").mkdir()
    (tmp_path / "logs" / "backend.log").write_text("x")

    assert not apply_pending_reset(tmp_path)             # nothing requested
    assert (tmp_path / "networks.json").exists()
    request_reset(tmp_path)
    assert apply_pending_reset(tmp_path)
    left = sorted(p.name for p in tmp_path.iterdir())
    assert left == ["config.toml", "logs", "tray.json"]
    assert (tmp_path / "logs" / "backend.log").exists()
    assert NetworkRegistry(tmp_path).list() == []
    assert not apply_pending_reset(tmp_path)             # once


def test_reset_api_needs_confirmation_then_restarts(api, tmp_path):
    client, ctx, _, _ = api
    ctx.data_root = tmp_path
    assert send(client, "POST", "/api/v1/reset").status_code == 400
    assert send(client, "POST", "/api/v1/reset", {"confirm": "yes"}).status_code == 400
    assert ctx.restarts == [] and not (tmp_path / "reset-pending").exists()
    response = send(client, "POST", "/api/v1/reset", {"confirm": "reset"})
    assert response.status_code == 202 and ctx.restarts == [1]
    assert (tmp_path / "reset-pending").exists()


def test_health_has_a_start_time(api):
    client, _, _, _ = api
    assert client.get("/api/v1/health").get_json()["started_at"].endswith("Z")


def test_capture_passes_interrupts_on_instead_of_swallowing_them(monkeypatch):
    import scapy.sendrecv
    from scapy.config import conf

    from netsleuth.core import capture

    seen = {}

    def fake_sniff(**kwargs):
        seen.update(kwargs)
        raise KeyboardInterrupt           # what chainCC=True makes scapy do on interrupt_main

    monkeypatch.setattr(scapy.sendrecv, "sniff", fake_sniff)
    monkeypatch.setattr(conf, "use_pcap", True, raising=False)
    with pytest.raises(KeyboardInterrupt):
        capture.run_capture("Wi-Fi", lambda p: None, stop=lambda: False)
    assert seen["chainCC"] is True
