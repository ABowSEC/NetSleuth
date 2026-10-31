import json
import os
import sqlite3
from typing import Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "devices.db")


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id          TEXT PRIMARY KEY,
                mac         TEXT,
                ip          TEXT,
                hostname    TEXT,
                first_seen  TEXT,
                last_seen   TEXT,
                dns_queries TEXT DEFAULT '[]',
                connections TEXT DEFAULT '[]',
                services    TEXT DEFAULT '[]'
            )
        """)


def load_devices() -> Dict[str, Any]:
    """Return device_log dict populated from the database."""
    init_db()
    devices = {}
    with _connect() as conn:
        for row in conn.execute("SELECT * FROM devices"):
            ip = row["ip"]
            if not ip:
                continue
            devices[ip] = {
                "mac":         row["mac"] or "Unknown",
                "hostname":    row["hostname"] or "Unknown",
                "first_seen":  row["first_seen"],
                "last_seen":   row["last_seen"],
                "dns_queries": json.loads(row["dns_queries"] or "[]"),
                "connections": json.loads(row["connections"] or "[]"),
                "services":    json.loads(row["services"] or "[]"),
            }
    print(f"[DB] Loaded {len(devices)} device(s) from storage.")
    return devices


def save_device(ip: str, data: Dict[str, Any]) -> None:
    """Upsert a single device record."""
    mac = data.get("mac") or "Unknown"
    row_id = mac if mac != "Unknown" else ip
    with _connect() as conn:
        conn.execute("""
            INSERT INTO devices (id, mac, ip, hostname, first_seen, last_seen, dns_queries, connections, services)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                ip          = excluded.ip,
                hostname    = excluded.hostname,
                last_seen   = excluded.last_seen,
                dns_queries = excluded.dns_queries,
                connections = excluded.connections,
                services    = excluded.services
        """, (
            row_id,
            mac,
            ip,
            data.get("hostname", "Unknown"),
            data.get("first_seen", data.get("last_seen")),
            data.get("last_seen"),
            json.dumps(data.get("dns_queries", [])),
            json.dumps(data.get("connections", [])),
            json.dumps(data.get("services", [])),
        ))
