import json
from ipaddress import ip_network

import pytest

from netsleuth.core.events import EventEngine
from netsleuth.core.pipeline import Pipeline
from netsleuth.core.store import DeviceStore
from netsleuth.settings import Settings
from netsleuth.web.api import AppContext, create_app

LAPTOP = "d0:57:7e:00:00:02"
PHONE = "02:11:22:33:44:55"
JSON = {"Content-Type": "application/json"}

DEVICE_KEYS = {"mac", "name", "hostname", "vendor", "type", "is_known", "online",
               "ips", "first_seen", "last_seen", "notes", "model", "os", "suggested_name"}


@pytest.fixture
def ctx(tmp_path):
    store = DeviceStore(tmp_path / "devices.db")
    engine = EventEngine(store)
    pipeline = Pipeline(store, ip_network("10.0.0.0/24"), observer=engine)
    context = AppContext(store=store, engine=engine, settings=Settings(), pipeline=pipeline,
                         interface="Wi-Fi", save_settings=False)
    yield context
    store.close()


@pytest.fixture
def client(ctx):
    return create_app(ctx).test_client()


@pytest.fixture
def seeded(ctx):
    ctx.store.observe(LAPTOP, "10.0.0.5")
    ctx.store.set_hostname(LAPTOP, "Den-ZenBook")
    ctx.store.observe(PHONE, "10.0.0.6")
    ctx.store.record_domain(LAPTOP, "example.com")
    return ctx


def patch(client, path, data, **kw):
    return client.patch(path, data=json.dumps(data), headers={**JSON, **kw.pop("headers", {})}, **kw)


# ── Status ───────────────────────────────────────────────────────────────

def test_health(client):
    body = client.get("/api/v1/health").get_json()
    assert body == {**body, "status": "ok", "capturing": True, "interface": "Wi-Fi"}


def test_pause_and_resume(client):
    assert client.post("/api/v1/capture/pause", headers=JSON).get_json()["capturing"] is False
    assert client.post("/api/v1/capture/resume", headers=JSON).get_json()["capturing"] is True


def test_summary(client, seeded):
    body = client.get("/api/v1/summary").get_json()
    assert (body["online"], body["unknown"], body["total"]) == (2, 2, 2)
    assert body["last_update"].endswith("Z")


# ── Devices ──────────────────────────────────────────────────────────────

def test_list_devices_matches_contract(client, seeded):
    devices = client.get("/api/v1/devices").get_json()
    assert {d["mac"] for d in devices} == {LAPTOP, PHONE}
    assert all(set(d) == DEVICE_KEYS for d in devices)
    assert client.get("/api/v1/devices?q=zenbook").get_json()[0]["mac"] == LAPTOP


@pytest.mark.parametrize("query", ["status=gone", "known=yes"])
def test_list_devices_rejects_bad_filters(client, query):
    assert client.get(f"/api/v1/devices?{query}").status_code == 400


def test_device_detail(client, seeded):
    body = client.get(f"/api/v1/devices/{LAPTOP.upper().replace(':', '-')}").get_json()
    assert body["mac"] == LAPTOP
    assert body["top_domains"][0]["domain"] == "example.com"
    assert {"top_destinations", "presence"} <= set(body)


def test_unknown_or_invalid_device_is_404(client):
    assert client.get(f"/api/v1/devices/{LAPTOP}").status_code == 404
    assert client.get("/api/v1/devices/not-a-mac").get_json()["error"] == "not_found"


def test_patch_device(client, seeded):
    body = patch(client, f"/api/v1/devices/{LAPTOP}", {"name": "  Zenbook  ", "is_known": True}).get_json()
    assert (body["name"], body["is_known"]) == ("Zenbook", True)
    body = patch(client, f"/api/v1/devices/{LAPTOP}", {"name": ""}).get_json()
    assert body["name"] is None and body["is_known"] is True


@pytest.mark.parametrize("data", [
    {"name": 5}, {"is_known": "yes"}, {"type": "tv"}, {"name": "x" * 65},
])
def test_patch_device_validation(client, seeded, data):
    resp = patch(client, f"/api/v1/devices/{LAPTOP}", data)
    assert resp.status_code == 400 and resp.get_json()["error"] == "bad_field"


def test_patch_non_object_body(client, seeded):
    resp = client.patch(f"/api/v1/devices/{LAPTOP}", data="[1]", headers=JSON)
    assert resp.status_code == 400


def test_delete_device(client, seeded):
    assert client.delete(f"/api/v1/devices/{PHONE}", headers=JSON).status_code == 204
    assert client.delete(f"/api/v1/devices/{PHONE}", headers=JSON).status_code == 404


# ── Write protection ─────────────────────────────────────────────────────

def test_writes_require_json_content_type(client, seeded):
    # A plain cross-site <form> POST can only send form or text types.
    resp = client.post("/api/v1/capture/pause", data="x", content_type="text/plain")
    assert resp.status_code == 415
    assert client.get("/api/v1/health").get_json()["capturing"] is True


def test_cross_origin_write_refused(client, seeded):
    resp = patch(client, f"/api/v1/devices/{LAPTOP}", {"name": "pwned"},
                 headers={"Origin": "http://evil.example"})
    assert resp.status_code == 403


def test_same_origin_write_allowed(client, seeded):
    resp = patch(client, f"/api/v1/devices/{LAPTOP}", {"name": "ok"}, headers={"Origin": "http://localhost"})
    assert resp.status_code == 200


def test_dev_origin_only_in_dev_mode(ctx, seeded):
    headers = {"Origin": "http://localhost:3000"}
    assert patch(create_app(ctx).test_client(), f"/api/v1/devices/{LAPTOP}", {"name": "a"},
                 headers=headers).status_code == 403
    ctx.dev = True
    assert patch(create_app(ctx).test_client(), f"/api/v1/devices/{LAPTOP}", {"name": "a"},
                 headers=headers).status_code == 200


# ── Events ───────────────────────────────────────────────────────────────

def test_events_list_and_filters(client, ctx):
    first = ctx.engine.emit("joined", "info", "a", mac=LAPTOP)
    ctx.engine.emit("alert", "high", "b", mac=PHONE)
    assert [e["message"] for e in client.get("/api/v1/events").get_json()] == ["b", "a"]
    assert [e["message"] for e in client.get(f"/api/v1/events?since={first['id']}").get_json()] == ["b"]
    assert [e["message"] for e in client.get("/api/v1/events?kind=joined").get_json()] == ["a"]
    assert [e["message"] for e in client.get(f"/api/v1/events?mac={PHONE.upper()}").get_json()] == ["b"]


@pytest.mark.parametrize("query", ["kind=boom", "limit=0", "limit=5000", "since=abc"])
def test_events_reject_bad_query(client, query):
    assert client.get(f"/api/v1/events?{query}").status_code == 400


def test_events_export_is_download(client, ctx):
    ctx.engine.emit("joined", "info", "a")
    resp = client.get("/api/v1/events/export")
    assert "attachment" in resp.headers["Content-Disposition"]
    assert resp.get_json()[0]["message"] == "a"


def test_stream_sends_summary_then_live_events(client, ctx):
    resp = client.get("/api/v1/stream", buffered=False)
    assert resp.mimetype == "text/event-stream"
    chunks = (c.decode() for c in resp.response)
    assert next(chunks).startswith("event: summary")
    ctx.engine.emit("new_device", "medium", "hello", mac=PHONE)
    received = ""
    for _ in range(5):
        received += next(chunks)
        if "hello" in received:
            break
    assert "event: event" in received and "hello" in received
    resp.close()
    assert ctx.engine._subscribers == []


def test_stream_replays_after_last_event_id(client, ctx):
    first = ctx.engine.emit("joined", "info", "missed-1")
    ctx.engine.emit("joined", "info", "missed-2")
    resp = client.get("/api/v1/stream", buffered=False, headers={"Last-Event-ID": str(first["id"])})
    chunk = next(iter(resp.response)).decode()
    assert "missed-2" in chunk and "missed-1" not in chunk
    resp.close()


# ── Settings ─────────────────────────────────────────────────────────────

def test_settings_round_trip(client, ctx):
    assert client.get("/api/v1/settings").get_json()["sweep_interval_s"] == 300
    body = patch(client, "/api/v1/settings", {"sweep_interval_s": 120}).get_json()
    assert body["sweep_interval_s"] == 120 and ctx.settings.sweep_interval_s == 120


def test_settings_invalid_patch_changes_nothing(client, ctx):
    resp = patch(client, "/api/v1/settings", {"sweep_interval_s": 120, "retention_days": 0})
    assert resp.status_code == 400
    assert ctx.settings.sweep_interval_s == 300


# ── Static UI ────────────────────────────────────────────────────────────

def test_static_ui_served_with_fallback(ctx, tmp_path):
    out = tmp_path / "out"
    (out / "_next").mkdir(parents=True)
    (out / "index.html").write_text("<h1>home</h1>")
    (out / "activity.html").write_text("<h1>activity</h1>")
    (out / "_next" / "app.js").write_text("js")
    ctx.static_dir = out
    client = create_app(ctx).test_client()

    assert b"home" in client.get("/").data
    assert b"activity" in client.get("/activity").data
    assert client.get("/_next/app.js").data == b"js"
    assert b"home" in client.get("/somewhere?device=x").data
    assert client.get("/api/v1/nope").status_code == 404


def test_unknown_api_route_is_json_404(client):
    resp = client.get("/api/v1/nope")
    assert resp.status_code == 404 and resp.get_json()["error"] == "not_found"


# ── Identify mode ────────────────────────────────────────────────────────

@pytest.fixture
def identify_client(ctx):
    import threading

    from netsleuth.core.identify_mode import IdentifySession, Probers

    release = threading.Event()
    probers = Probers(
        ssdp_search=lambda ip: release.wait(5) and {},
        fetch_description=lambda url, net: {},
        mdns_query=lambda ip: 0,
        netbios_name=lambda ip: "DESKTOP-4FJ2K9Q",
        reverse_dns=lambda ip: None,
        port_check=lambda ip: [],
        http_title=lambda ip, port: None,
    )
    ctx.store.observe(LAPTOP, "10.0.0.5")
    ctx.identify = IdentifySession(ctx.store, ctx.engine, ip_network("10.0.0.0/24"), "10.0.0.2",
                                   is_paused=lambda: ctx.pipeline.paused, probers=probers, spacing=0)
    yield create_app(ctx).test_client(), ctx, release
    release.set()
    ctx.identify.stop()


def post(client, path, data=None):
    return client.post(path, data=json.dumps(data or {}), headers=JSON)


def test_identify_idle_and_unavailable_without_session(client):
    assert client.get("/api/v1/identify").get_json()["running"] is False
    assert post(client, "/api/v1/identify/start").status_code == 503


def test_identify_start_conflict_and_stop(identify_client):
    client, ctx, release = identify_client
    status = post(client, "/api/v1/identify/start", {"minutes": 5}).get_json()
    assert status["running"] and status["total"] == 1
    assert client.get("/api/v1/identify").get_json()["running"] is True
    assert post(client, "/api/v1/identify/start").status_code == 409
    release.set()
    post(client, "/api/v1/identify/stop")
    assert client.get("/api/v1/identify").get_json()["running"] is False
    assert ctx.store.list_events(kind="identified")


def test_identify_refused_while_paused(identify_client):
    client, ctx, _ = identify_client
    ctx.pipeline.pause()
    resp = post(client, "/api/v1/identify/start")
    assert resp.status_code == 423 and resp.get_json()["error"] == "monitoring_paused"


@pytest.mark.parametrize("data", [{"minutes": 0}, {"minutes": 31}, {"minutes": "5"}, {"minutes": True},
                                  {"macs": "aa:bb"}, {"macs": ["nope"]}, {"other": 1}])
def test_identify_start_validation(identify_client, data):
    client, _, _ = identify_client
    assert post(client, "/api/v1/identify/start", data).status_code == 400


def test_identify_start_accepts_specific_macs(identify_client):
    client, ctx, release = identify_client
    ctx.store.observe(PHONE, "10.0.0.6")
    status = post(client, "/api/v1/identify/start", {"macs": [PHONE.upper().replace(":", "-")]}).get_json()
    assert status["total"] == 1
    release.set()


def test_stream_carries_identify_progress(identify_client):
    client, ctx, release = identify_client
    resp = client.get("/api/v1/stream", buffered=False)
    chunks = (c.decode() for c in resp.response)
    next(chunks)  # summary
    post(client, "/api/v1/identify/start")
    received = ""
    for _ in range(10):
        received += next(chunks)
        if "event: identify" in received:
            break
    assert "event: identify" in received and '"running": true' in received
    release.set()
    resp.close()


def test_identified_is_a_valid_event_kind(client):
    assert client.get("/api/v1/events?kind=identified").status_code == 200


def test_identify_settings(client, ctx):
    body = patch(client, "/api/v1/settings", {"port_check": True, "identify_minutes": 20}).get_json()
    assert body["port_check"] is True and body["identify_minutes"] == 20
    assert patch(client, "/api/v1/settings", {"identify_minutes": 3}).status_code == 400
