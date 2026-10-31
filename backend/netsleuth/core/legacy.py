"""One-time import of data from pre-0.2 NetSleuth.

Only device names from ``known_devices.json`` are carried over. The old
``devices.db`` is not migrated (its rows were keyed inconsistently and mixed
remote IPs into the router's record); it is renamed to ``devices.db.bak``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from ..timeutil import iso, utcnow
from ..utils.mac import normalize_mac
from .store import DeviceStore

log = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[2]
LEGACY_KNOWN_JSON = _BACKEND_DIR / "netsleuth" / "config" / "known_devices.json"
LEGACY_DB = _BACKEND_DIR / "data" / "devices.db"


def _names_from(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Could not read legacy %s: %s", path, e)
        return {}

    names = {}
    # Both historical schemas: {"mac": {mac: "Name"}} and {"mac": {mac: {"name": "Name"}}}
    for key, value in (data.get("mac") or {}).items():
        mac = normalize_mac(key)
        name = value.get("name") if isinstance(value, dict) else value
        if mac and isinstance(name, str) and name.strip():
            names[mac] = name.strip()
    return names


def import_legacy(store: DeviceStore, known_json: Path = LEGACY_KNOWN_JSON, old_db: Path = LEGACY_DB) -> int:
    """Import legacy names once. Returns the number of devices imported."""
    if store.get_meta("legacy_imported"):
        return 0

    names = _names_from(known_json)
    for mac, name in names.items():
        store.import_known(mac, name)

    if old_db.exists():
        backup = old_db.with_name(old_db.name + ".bak")
        try:
            old_db.replace(backup)
            log.info("Old database moved to %s (not migrated)", backup)
        except OSError as e:
            log.warning("Could not rename old database %s: %s", old_db, e)

    store.set_meta("legacy_imported", iso(utcnow()))
    if names:
        log.info("Imported %d named device(s) from %s", len(names), known_json)
    return len(names)
