import json
import sqlite3
from datetime import timedelta

import pytest

from netsleuth.core import store as store_mod
from netsleuth.core.legacy import import_legacy
from netsleuth.core.store import DeviceStore
from netsleuth.timeutil import iso, utcnow

PHONE = "02:11:22:33:44:55"     # randomized (locally administered)
LAPTOP = "d0:57:7e:00:00:02"
ROUTER = "f4:c1:14:00:00:01"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "devices.db"


@pytest.fixture
def store(db_path):
    s = DeviceStore(db_path)
    yield s
    s.close()


def reopen(store, db_path):
    store.close()
    return DeviceStore(db_path)


def test_new_device_observation(store):
    obs = store.observe(LAPTOP, "10.0.0.5")
    assert obs.is_new and obs.came_online
    again = store.observe(LAPTOP, "10.0.0.5")
    assert not again.is_new and not again.came_online
    device = store.get(LAPTOP)
    assert device.online and device.ips == ["10.0.0.5"]


def test_ip_change_and_ip_takeover(store):
    store.observe(LAPTOP, "10.0.0.5")
    obs = store.observe(LAPTOP, "10.0.0.9")
    assert obs.previous_ip == "10.0.0.5"
    assert store.get(LAPTOP).ips == ["10.0.0.9", "10.0.0.5"]

    takeover = store.observe(PHONE, "10.0.0.9")
    assert takeover.ip_taken_from == LAPTOP
    assert store.mac_for_ip("10.0.0.9") == PHONE


def test_state_survives_restart(store, db_path):
    store.observe(LAPTOP, "10.0.0.5")
    store.set_hostname(LAPTOP, "Den-ZenBook")
    store.update(LAPTOP, name="Zenbook", is_known=True, notes="desk")
    store.record_domain(LAPTOP, "Example.COM.")
    store.record_domain(LAPTOP, "example.com")
    store.record_destination(LAPTOP, "93.184.216.34", 443)

    reloaded = reopen(store, db_path)
    try:
        device = reloaded.get(LAPTOP)
        assert (device.name, device.is_known, device.notes) == ("Zenbook", True, "desk")
        assert device.hostname == "Den-ZenBook"
        assert device.type == "computer"
        assert device.ips == ["10.0.0.5"]
        assert device.online is False  # nothing is online until seen again

        detail = reloaded.detail(LAPTOP)
        assert detail["top_domains"][0]["domain"] == "example.com"
        assert detail["top_domains"][0]["count"] == 2
        assert detail["top_destinations"][0]["port"] == 443
        assert detail["presence"][0]["end"] is not None  # session closed on reload
    finally:
        reloaded.close()


def test_counts_accumulate_across_flushes(store):
    store.observe(LAPTOP)
    store.record_destination(LAPTOP, "1.1.1.1", None)
    store.flush()
    store.record_destination(LAPTOP, "1.1.1.1", None)
    dest = store.detail(LAPTOP)["top_destinations"][0]
    assert dest == {**dest, "address": "1.1.1.1", "port": None, "count": 2}


def test_records_for_unseen_device_are_ignored(store):
    store.record_domain(LAPTOP, "example.com")
    store.flush()
    assert store.get(LAPTOP) is None


def test_expire_marks_offline_and_closes_session(store):
    past = utcnow() - timedelta(minutes=30)
    store.observe(LAPTOP, "10.0.0.5", ts=past)
    store.observe(PHONE, "10.0.0.6")
    gone = store.expire(timeout_s=600)
    assert [d.mac for d in gone] == [LAPTOP]
    assert not store.get(LAPTOP).online
    assert store.get(PHONE).online

    assert store.observe(LAPTOP).came_online
    sessions = store.detail(LAPTOP)["presence"]
    assert len(sessions) == 2 and sessions[0]["end"] == iso(past)


def test_forget_removes_history(store, db_path):
    store.observe(LAPTOP, "10.0.0.5")
    store.record_domain(LAPTOP, "example.com")
    store.add_event("new_device", "medium", "New device", mac=LAPTOP)
    assert store.forget(LAPTOP)
    store.flush()
    assert store.get(LAPTOP) is None
    assert store.mac_for_ip("10.0.0.5") is None
    assert store.list_events(mac=LAPTOP) == []
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM domain_counts").fetchone()[0] == 0
    assert not store.forget(LAPTOP)


def test_events_filter_and_order(store):
    first = store.add_event("joined", "info", "a", mac=LAPTOP)
    store.add_event("left", "info", "b", mac=PHONE)
    third = store.add_event("joined", "info", "c", mac=PHONE, data={"ip": "10.0.0.6"})

    assert [e["message"] for e in store.list_events()] == ["c", "b", "a"]
    assert [e["id"] for e in store.list_events(since=first["id"])] == [third["id"], third["id"] - 1]
    assert [e["message"] for e in store.list_events(kind="joined")] == ["c", "a"]
    assert store.list_events(mac=PHONE, limit=1)[0]["data"] == {"ip": "10.0.0.6"}


def test_list_devices_filters(store):
    store.observe(LAPTOP, "10.0.0.5")
    store.observe(PHONE, "10.0.0.6", ts=utcnow() - timedelta(hours=1))
    store.expire(timeout_s=600)
    store.update(LAPTOP, name="Zenbook", is_known=True)

    assert [d.mac for d in store.list_devices(status="online")] == [LAPTOP]
    assert [d.mac for d in store.list_devices(status="offline")] == [PHONE]
    assert [d.mac for d in store.list_devices(known=False)] == [PHONE]
    assert [d.mac for d in store.list_devices(q="zen")] == [LAPTOP]
    assert [d.mac for d in store.list_devices(q="10.0.0.6")] == [PHONE]
    assert store.summary() | {"last_update": None} == {
        "online": 1, "offline": 1, "unknown": 1, "total": 2, "last_update": None,
    }


def test_gateway_stays_router_after_hostname(store):
    store.observe(ROUTER, "10.0.0.1")
    store.mark_gateway(ROUTER)
    store.set_hostname(ROUTER, "my-pc")
    assert store.get(ROUTER).type == "router"


def test_prune_drops_old_history(store):
    old = utcnow() - timedelta(days=40)
    store.observe(LAPTOP, ts=old)
    store.record_domain(LAPTOP, "old.example", ts=old)
    store.add_event("joined", "info", "old", mac=LAPTOP, ts=old)
    store.record_domain(LAPTOP, "new.example")
    store.prune(retention_days=30)
    detail = store.detail(LAPTOP)
    assert [d["domain"] for d in detail["top_domains"]] == ["new.example"]
    assert store.list_events() == []
    assert store.get(LAPTOP) is not None  # inventory itself is kept


def test_newer_schema_is_refused(db_path):
    DeviceStore(db_path).close()
    with sqlite3.connect(db_path) as conn:
        conn.execute("UPDATE meta SET value = '99' WHERE key = 'schema_version'")
    with pytest.raises(RuntimeError, match="newer"):
        DeviceStore(db_path)


def test_flusher_thread_persists(store, db_path, monkeypatch):
    store._flush_interval = 0.05
    store.start()
    store.observe(LAPTOP)
    import time
    deadline = time.time() + 2
    while time.time() < deadline:
        with sqlite3.connect(db_path) as conn:
            if conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]:
                break
        time.sleep(0.05)
    else:
        pytest.fail("flusher never wrote the device")


# ── Legacy import ──────────────────────────────────────────────────────────

def test_legacy_import_both_schemas(store, tmp_path):
    known = tmp_path / "known_devices.json"
    known.write_text(json.dumps({
        "ip": {"10.0.0.7": "Ignored"},
        "mac": {
            "D0-57-7E-00-00-02": {"name": "Study laptop"},
            "f4:c1:14:00:00:01": "Router",
            "10.0.0.8": {"name": "IP-keyed claim"},   # not a MAC: skipped
            "aa:bb:cc:dd:ee:00": {"name": "  "},      # blank name: skipped
        },
    }), encoding="utf-8")
    old_db = tmp_path / "old.db"
    old_db.write_bytes(b"x")

    assert import_legacy(store, known, old_db) == 2
    assert store.get(LAPTOP).name == "Study laptop" and store.get(LAPTOP).is_known
    assert store.get(ROUTER).name == "Router"
    assert not old_db.exists() and (tmp_path / "old.db.bak").exists()

    # Runs only once
    assert import_legacy(store, known, old_db) == 0


def test_legacy_import_tolerates_missing_and_corrupt(store, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    assert import_legacy(store, bad, tmp_path / "none.db") == 0
    assert store.get_meta("legacy_imported")


def test_schema_version_constant_matches_migrations():
    assert max(store_mod._MIGRATIONS) == store_mod.SCHEMA_VERSION
