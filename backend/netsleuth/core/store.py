"""Device inventory: in-memory state backed by SQLite.

A device is identified by its MAC address. IPs are attributes of a device
(with history), never identities.

Threading model
- Every public method is thread-safe.
- Hot-path calls (``observe``, ``record_domain``, ``record_destination``)
  only touch memory. A flusher thread writes dirty state to SQLite every
  ``flush_interval`` seconds in one transaction.
- Low-frequency writes (events, user edits, forget) go to SQLite immediately.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timedelta
from pathlib import Path

from ..timeutil import iso, parse_iso, utcnow
from ..utils.classify import classify
from ..utils.mac import vendor_for

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
MAX_IPS_PER_DEVICE = 10
TOP_N = 20

_SCHEMA_V1 = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE devices (
    mac        TEXT PRIMARY KEY,
    name       TEXT,
    hostname   TEXT,
    vendor     TEXT,
    type       TEXT NOT NULL DEFAULT 'unknown',
    is_known   INTEGER NOT NULL DEFAULT 0,
    notes      TEXT,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL
);

CREATE TABLE device_ips (
    mac        TEXT NOT NULL REFERENCES devices(mac) ON DELETE CASCADE,
    ip         TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen  TEXT NOT NULL,
    PRIMARY KEY (mac, ip)
);
CREATE INDEX ix_device_ips_ip ON device_ips(ip);

CREATE TABLE sessions (
    id    INTEGER PRIMARY KEY,
    mac   TEXT NOT NULL REFERENCES devices(mac) ON DELETE CASCADE,
    start TEXT NOT NULL,
    end   TEXT
);
CREATE INDEX ix_sessions_mac ON sessions(mac, start);

CREATE TABLE events (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       TEXT NOT NULL,
    kind     TEXT NOT NULL,
    mac      TEXT,
    severity TEXT NOT NULL,
    message  TEXT NOT NULL,
    data     TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX ix_events_ts ON events(ts);
CREATE INDEX ix_events_mac ON events(mac);

CREATE TABLE domain_counts (
    mac       TEXT NOT NULL REFERENCES devices(mac) ON DELETE CASCADE,
    domain    TEXT NOT NULL,
    count     INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (mac, domain)
);

CREATE TABLE dest_counts (
    mac       TEXT NOT NULL REFERENCES devices(mac) ON DELETE CASCADE,
    address   TEXT NOT NULL,
    port      INTEGER NOT NULL,   -- -1 when not applicable
    count     INTEGER NOT NULL,
    last_seen TEXT NOT NULL,
    PRIMARY KEY (mac, address, port)
);
"""

# version -> SQL that upgrades from version-1. Add entries as the schema evolves.
_MIGRATIONS: dict[int, str] = {1: _SCHEMA_V1}

_UNSET = object()


@dataclass
class Device:
    mac: str
    first_seen: str
    last_seen: str
    name: str | None = None
    hostname: str | None = None
    vendor: str | None = None
    type: str = "unknown"
    is_known: bool = False
    notes: str | None = None
    online: bool = False
    ips: list[str] = field(default_factory=list)  # most recent first
    is_gateway: bool = False                      # internal, not in the API

    def to_api(self) -> dict:
        data = asdict(self)
        del data["is_gateway"]
        return data

    def copy(self) -> "Device":
        return replace(self, ips=list(self.ips))


@dataclass(frozen=True)
class Observation:
    is_new: bool                       # first time this MAC was ever seen
    came_online: bool                  # was offline (or new) until now
    previous_ip: str | None = None     # set when the device's current IP changed
    ip_taken_from: str | None = None   # MAC that previously held this IP


class DeviceStore:
    def __init__(self, db_path: Path, flush_interval: float = 2.0):
        self._lock = threading.RLock()       # in-memory state
        self._db_lock = threading.Lock()     # the SQLite connection
        self._flush_interval = flush_interval
        self._stop = threading.Event()
        self._flusher: threading.Thread | None = None

        self._devices: dict[str, Device] = {}
        self._ip_owner: dict[str, str] = {}
        self._dirty_devices: set[str] = set()
        self._dirty_ips: dict[tuple[str, str], str] = {}
        self._session_ops: list[tuple[str, str, str]] = []   # (open|close, mac, ts)
        self._pending_domains: dict[tuple[str, str], list] = {}
        self._pending_dests: dict[tuple[str, str, int], list] = {}

        self._conn = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()
        self._load()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._flusher is None:
            self._flusher = threading.Thread(target=self._flush_loop, name="store-flush", daemon=True)
            self._flusher.start()

    def close(self) -> None:
        self._stop.set()
        if self._flusher:
            self._flusher.join(timeout=5)
            self._flusher = None
        self.flush()
        with self._db_lock:
            self._conn.close()

    def _flush_loop(self) -> None:
        while not self._stop.wait(self._flush_interval):
            try:
                self.flush()
            except Exception:
                log.exception("Store flush failed")

    def _migrate(self) -> None:
        with self._db_lock, self._conn:
            has_meta = self._conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'"
            ).fetchone()
            current = 0
            if has_meta:
                row = self._conn.execute("SELECT value FROM meta WHERE key='schema_version'").fetchone()
                current = int(row["value"]) if row else 0
            if current > SCHEMA_VERSION:
                raise RuntimeError(f"Database schema v{current} is newer than this NetSleuth (v{SCHEMA_VERSION})")
            for version in range(current + 1, SCHEMA_VERSION + 1):
                log.info("Migrating database to schema v%d", version)
                self._conn.executescript(_MIGRATIONS[version])
                self._conn.execute(
                    "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)", (str(version),)
                )

    def _load(self) -> None:
        with self._db_lock, self._conn:
            # Anything "online" when we last stopped ended at its last sighting.
            self._conn.execute(
                "UPDATE sessions SET end = (SELECT last_seen FROM devices d WHERE d.mac = sessions.mac) "
                "WHERE end IS NULL"
            )
            for row in self._conn.execute("SELECT * FROM devices"):
                self._devices[row["mac"]] = Device(
                    mac=row["mac"], first_seen=row["first_seen"], last_seen=row["last_seen"],
                    name=row["name"], hostname=row["hostname"], vendor=row["vendor"],
                    type=row["type"], is_known=bool(row["is_known"]), notes=row["notes"],
                )
            for row in self._conn.execute("SELECT mac, ip FROM device_ips ORDER BY last_seen"):
                device = self._devices.get(row["mac"])
                if device:
                    device.ips.insert(0, row["ip"])
                    self._ip_owner[row["ip"]] = row["mac"]
        for device in self._devices.values():
            del device.ips[MAX_IPS_PER_DEVICE:]
        log.info("Loaded %d device(s) from storage", len(self._devices))

    # ── Hot path (memory only) ───────────────────────────────────────────────

    def observe(self, mac: str, ip: str | None = None, ts: datetime | None = None) -> Observation:
        """Record that ``mac`` was seen (optionally using ``ip``) at ``ts``."""
        stamp = iso(ts or utcnow())
        with self._lock:
            device = self._devices.get(mac)
            is_new = device is None
            if is_new:
                vendor = vendor_for(mac)
                device = Device(mac=mac, first_seen=stamp, last_seen=stamp,
                                vendor=vendor, type=classify(None, vendor))
                self._devices[mac] = device

            device.last_seen = max(device.last_seen, stamp)
            came_online = not device.online
            if came_online:
                device.online = True
                self._session_ops.append(("open", mac, stamp))

            previous_ip = ip_taken_from = None
            if ip:
                if device.ips and device.ips[0] != ip:
                    previous_ip = device.ips[0]
                if ip in device.ips:
                    device.ips.remove(ip)
                device.ips.insert(0, ip)
                del device.ips[MAX_IPS_PER_DEVICE:]

                owner = self._ip_owner.get(ip)
                if owner and owner != mac:
                    ip_taken_from = owner
                self._ip_owner[ip] = mac
                self._dirty_ips[(mac, ip)] = stamp

            self._dirty_devices.add(mac)
            return Observation(is_new, came_online, previous_ip, ip_taken_from)

    def set_hostname(self, mac: str, hostname: str) -> None:
        hostname = hostname.strip()
        with self._lock:
            device = self._devices.get(mac)
            if not device or not hostname or hostname == device.hostname:
                return
            device.hostname = hostname
            device.type = classify(hostname, device.vendor, device.is_gateway)
            self._dirty_devices.add(mac)

    def mark_gateway(self, mac: str) -> None:
        with self._lock:
            device = self._devices.get(mac)
            if device and not device.is_gateway:
                device.is_gateway = True
                device.type = "router"
                self._dirty_devices.add(mac)

    def record_domain(self, mac: str, domain: str, ts: datetime | None = None) -> None:
        domain = domain.strip().rstrip(".").lower()
        if not domain:
            return
        stamp = iso(ts or utcnow())
        with self._lock:
            if mac not in self._devices:
                return
            entry = self._pending_domains.setdefault((mac, domain), [0, stamp])
            entry[0] += 1
            entry[1] = max(entry[1], stamp)

    def record_destination(self, mac: str, address: str, port: int | None, ts: datetime | None = None) -> None:
        stamp = iso(ts or utcnow())
        key = (mac, address, -1 if port is None else port)
        with self._lock:
            if mac not in self._devices:
                return
            entry = self._pending_dests.setdefault(key, [0, stamp])
            entry[0] += 1
            entry[1] = max(entry[1], stamp)

    def expire(self, timeout_s: int, now: datetime | None = None) -> list[Device]:
        """Mark devices silent for ``timeout_s`` as offline; return them."""
        cutoff = (now or utcnow()) - timedelta(seconds=timeout_s)
        gone = []
        with self._lock:
            for device in self._devices.values():
                if device.online and parse_iso(device.last_seen) < cutoff:
                    device.online = False
                    self._session_ops.append(("close", device.mac, device.last_seen))
                    gone.append(device.copy())
        return gone

    # ── Persistence ──────────────────────────────────────────────────────────

    def flush(self) -> None:
        with self._lock:
            devices = [self._devices[m].copy() for m in self._dirty_devices if m in self._devices]
            ips, sessions = self._dirty_ips, self._session_ops
            domains, dests = self._pending_domains, self._pending_dests
            self._dirty_devices, self._dirty_ips, self._session_ops = set(), {}, []
            self._pending_domains, self._pending_dests = {}, {}

        if not (devices or ips or sessions or domains or dests):
            return

        with self._db_lock, self._conn:
            # A device forgotten after the swap above must not be written back.
            with self._lock:
                live = set(self._devices)
            devices = [d for d in devices if d.mac in live]
            ips = {k: v for k, v in ips.items() if k[0] in live}
            sessions = [op for op in sessions if op[1] in live]
            domains = {k: v for k, v in domains.items() if k[0] in live}
            dests = {k: v for k, v in dests.items() if k[0] in live}

            self._upsert_devices(devices)
            self._conn.executemany(
                "INSERT INTO device_ips(mac, ip, first_seen, last_seen) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(mac, ip) DO UPDATE SET last_seen = MAX(last_seen, excluded.last_seen)",
                [(mac, ip, ts, ts) for (mac, ip), ts in ips.items()],
            )
            for op, mac, ts in sessions:
                if op == "open":
                    self._conn.execute("INSERT INTO sessions(mac, start) VALUES (?, ?)", (mac, ts))
                else:
                    self._conn.execute("UPDATE sessions SET end = ? WHERE mac = ? AND end IS NULL", (ts, mac))
            self._conn.executemany(
                "INSERT INTO domain_counts(mac, domain, count, last_seen) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(mac, domain) DO UPDATE SET count = count + excluded.count, "
                "last_seen = MAX(last_seen, excluded.last_seen)",
                [(mac, domain, n, ts) for (mac, domain), (n, ts) in domains.items()],
            )
            self._conn.executemany(
                "INSERT INTO dest_counts(mac, address, port, count, last_seen) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(mac, address, port) DO UPDATE SET count = count + excluded.count, "
                "last_seen = MAX(last_seen, excluded.last_seen)",
                [(mac, addr, port, n, ts) for (mac, addr, port), (n, ts) in dests.items()],
            )

    def _upsert_devices(self, devices: list[Device]) -> None:
        """Caller holds _db_lock inside a transaction."""
        self._conn.executemany(
            "INSERT INTO devices(mac, name, hostname, vendor, type, is_known, notes, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(mac) DO UPDATE SET name = excluded.name, hostname = excluded.hostname, "
            "vendor = excluded.vendor, type = excluded.type, is_known = excluded.is_known, "
            "notes = excluded.notes, last_seen = excluded.last_seen",
            [(d.mac, d.name, d.hostname, d.vendor, d.type, int(d.is_known), d.notes, d.first_seen, d.last_seen)
             for d in devices],
        )

    # ── User edits (written immediately) ─────────────────────────────────────

    def update(self, mac: str, *, name=_UNSET, is_known=_UNSET, notes=_UNSET) -> Device | None:
        with self._lock:
            device = self._devices.get(mac)
            if not device:
                return None
            if name is not _UNSET:
                device.name = name
            if is_known is not _UNSET:
                device.is_known = is_known
            if notes is not _UNSET:
                device.notes = notes
            self._dirty_devices.discard(mac)
            snapshot = device.copy()
        with self._db_lock, self._conn:
            self._upsert_devices([snapshot])
        return snapshot

    def import_known(self, mac: str, name: str) -> None:
        """Create or update a device as known with ``name`` (legacy import)."""
        stamp = iso(utcnow())
        with self._lock:
            if mac not in self._devices:
                vendor = vendor_for(mac)
                self._devices[mac] = Device(mac=mac, first_seen=stamp, last_seen=stamp,
                                            vendor=vendor, type=classify(None, vendor))
        self.update(mac, name=name, is_known=True)

    def forget(self, mac: str) -> bool:
        """Remove a device and all of its history."""
        with self._lock:
            device = self._devices.pop(mac, None)
            if not device:
                return False
            for ip in device.ips:
                if self._ip_owner.get(ip) == mac:
                    del self._ip_owner[ip]
            self._dirty_devices.discard(mac)
            self._dirty_ips = {k: v for k, v in self._dirty_ips.items() if k[0] != mac}
            self._session_ops = [op for op in self._session_ops if op[1] != mac]
            self._pending_domains = {k: v for k, v in self._pending_domains.items() if k[0] != mac}
            self._pending_dests = {k: v for k, v in self._pending_dests.items() if k[0] != mac}
        with self._db_lock, self._conn:
            self._conn.execute("DELETE FROM devices WHERE mac = ?", (mac,))
            self._conn.execute("DELETE FROM events WHERE mac = ?", (mac,))
        return True

    # ── Events ───────────────────────────────────────────────────────────────

    def add_event(self, kind: str, severity: str, message: str,
                  mac: str | None = None, data: dict | None = None, ts: datetime | None = None) -> dict:
        stamp = iso(ts or utcnow())
        payload = data or {}
        with self._db_lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO events(ts, kind, mac, severity, message, data) VALUES (?, ?, ?, ?, ?, ?)",
                (stamp, kind, mac, severity, message, json.dumps(payload)),
            )
        return {"id": cur.lastrowid, "ts": stamp, "kind": kind, "mac": mac,
                "severity": severity, "message": message, "data": payload}

    def list_events(self, since: int | None = None, limit: int = 100,
                    kind: str | None = None, mac: str | None = None) -> list[dict]:
        clauses, params = [], []
        if since is not None:
            clauses.append("id > ?")
            params.append(since)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)
        if mac:
            clauses.append("mac = ?")
            params.append(mac)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._db_lock:
            rows = self._conn.execute(
                f"SELECT * FROM events {where} ORDER BY id DESC LIMIT ?", (*params, limit)
            ).fetchall()
        return [{**dict(row), "data": json.loads(row["data"])} for row in rows]

    # ── Reads ────────────────────────────────────────────────────────────────

    def get(self, mac: str) -> Device | None:
        with self._lock:
            device = self._devices.get(mac)
            return device.copy() if device else None

    def mac_for_ip(self, ip: str) -> str | None:
        with self._lock:
            return self._ip_owner.get(ip)

    def list_devices(self, status: str = "all", known: bool | None = None, q: str | None = None) -> list[Device]:
        needle = (q or "").strip().lower()
        with self._lock:
            result = [d.copy() for d in self._devices.values()]
        if status == "online":
            result = [d for d in result if d.online]
        elif status == "offline":
            result = [d for d in result if not d.online]
        if known is not None:
            result = [d for d in result if d.is_known == known]
        if needle:
            result = [
                d for d in result
                if any(needle in (v or "").lower() for v in (d.name, d.hostname, d.vendor, d.mac, *d.ips))
            ]
        result.sort(key=lambda d: d.last_seen, reverse=True)
        return result

    def detail(self, mac: str, now: datetime | None = None) -> dict | None:
        device = self.get(mac)
        if not device:
            return None
        self.flush()
        week_ago = iso((now or utcnow()) - timedelta(days=7))
        with self._db_lock:
            domains = self._conn.execute(
                "SELECT domain, count, last_seen FROM domain_counts WHERE mac = ? "
                "ORDER BY count DESC LIMIT ?", (mac, TOP_N)).fetchall()
            dests = self._conn.execute(
                "SELECT address, port, count, last_seen FROM dest_counts WHERE mac = ? "
                "ORDER BY count DESC LIMIT ?", (mac, TOP_N)).fetchall()
            sessions = self._conn.execute(
                "SELECT start, end FROM sessions WHERE mac = ? AND (end IS NULL OR end >= ?) "
                "ORDER BY start", (mac, week_ago)).fetchall()
        return {
            **device.to_api(),
            "top_domains": [dict(r) for r in domains],
            "top_destinations": [{**dict(r), "port": None if r["port"] < 0 else r["port"]} for r in dests],
            "presence": [dict(r) for r in sessions],
        }

    def summary(self) -> dict:
        with self._lock:
            devices = list(self._devices.values())
            online = sum(d.online for d in devices)
            return {
                "online": online,
                "offline": len(devices) - online,
                "unknown": sum(not d.is_known for d in devices),
                "total": len(devices),
                "last_update": iso(utcnow()),
            }

    # ── Housekeeping ─────────────────────────────────────────────────────────

    def prune(self, retention_days: int, now: datetime | None = None) -> None:
        cutoff = iso((now or utcnow()) - timedelta(days=retention_days))
        self.flush()
        with self._db_lock, self._conn:
            self._conn.execute("DELETE FROM events WHERE ts < ?", (cutoff,))
            self._conn.execute("DELETE FROM sessions WHERE end IS NOT NULL AND end < ?", (cutoff,))
            self._conn.execute("DELETE FROM domain_counts WHERE last_seen < ?", (cutoff,))
            self._conn.execute("DELETE FROM dest_counts WHERE last_seen < ?", (cutoff,))

    def get_meta(self, key: str) -> str | None:
        with self._db_lock:
            row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        with self._db_lock, self._conn:
            self._conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)", (key, value))
