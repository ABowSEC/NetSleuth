"""Network profiles: which network is this, and how much may NetSleuth do on it?

Each network keeps its own device inventory, so devices from a school or a
café never mix with the home list (see docs/ROADMAP.md).

Identity: a network is its router, as **gateway MAC + subnet**. The SSID is a
label and a supporting clue only: names repeat (eduroam, xfinitywifi) and
anyone can broadcast yours. Nothing here sends packets: the gateway MAC comes
from the OS ARP cache, the SSID from ``netsh wlan``.

Trust, per network:
- ``home``: capture, ARP sweep, Identify, alerts and notifications.
- ``observe``: passive capture only. No sweep, no Identify.
- ``idle``: nothing; capture is not even opened. Every new network starts here.

Layout under the data dir::

    networks.json                index: every known network and its trust
    networks/<id>/devices.db     that network's inventory
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass, field, replace
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Callable

from ..timeutil import iso, utcnow
from ..utils.mac import normalize_mac

log = logging.getLogger(__name__)

TRUST_LEVELS = ("home", "observe", "idle")
DEFAULT_TRUST = "idle"
LABEL_MAX = 64
MAX_BSSIDS = 16
WATCH_INTERVAL_S = 15

_UNSET = object()
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)   # the tray runs without a console
_IP = r"\d{1,3}(?:\.\d{1,3}){3}"
_MAC = r"[0-9a-fA-F]{2}(?:[-:][0-9a-fA-F]{2}){5}"


# ── Fingerprint ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Fingerprint:
    """What this PC can see of the network it's on, without sending anything."""
    subnet: str
    own_ip: str
    gateway_ip: str | None = None
    gateway_mac: str | None = None
    ssid: str | None = None
    bssid: str | None = None

    @property
    def id(self) -> str:
        if self.gateway_mac:
            key = f"{self.gateway_mac}|{self.subnet}"
        else:   # no router seen (an isolated LAN): fall back to subnet and name
            key = f"nogw|{self.subnet}|{self.ssid or ''}"
        return hashlib.sha256(key.encode()).hexdigest()[:12]

    def same_network(self, other: "Fingerprint") -> bool:
        """False only when ``other`` is positively a different network (or address)."""
        if other.subnet != self.subnet or other.own_ip != self.own_ip:
            return False
        if self.gateway_mac and other.gateway_mac and self.gateway_mac != other.gateway_mac:
            return False
        return True


def _run(cmd: list[str], timeout: float = 5.0) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                creationflags=_NO_WINDOW, errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        log.debug("%s failed: %s", cmd[0], e)
        return ""
    return result.stdout or ""


def parse_arp_cache(text: str, ip: str) -> str | None:
    """MAC for ``ip`` in ``arp -a`` (Windows) or ``ip neigh`` (Linux) output."""
    for line in text.splitlines():
        fields_ = line.split()
        if ip in fields_:
            match = re.search(_MAC, line)
            if match:
                return normalize_mac(match.group(0))
    return None


def arp_cache_mac(ip: str, own_ip: str | None = None) -> str | None:
    """Look ``ip`` up in the OS neighbour cache. Sends nothing."""
    if sys.platform == "win32":
        cmd = ["arp", "-a", ip] + (["-N", own_ip] if own_ip else [])
    else:
        cmd = ["ip", "neigh", "show", ip]
    return parse_arp_cache(_run(cmd), ip)


def parse_wlan_interfaces(text: str, iface_mac: str | None) -> tuple[str | None, str | None]:
    """(SSID, BSSID) from ``netsh wlan show interfaces`` for the adapter with ``iface_mac``.

    Keys other than SSID/BSSID are localised, so the adapter's block is found by
    its MAC address. With one connected adapter and no MAC match, that one is used.
    """
    blocks, current = [], {}
    for line in text.splitlines():
        key, sep, value = line.partition(" : ")
        if not sep:
            key, sep, value = line.partition(": ")
        key, value = key.strip(), value.strip()
        if not sep or not key:
            if current:
                blocks.append(current)
                current = {}
            continue
        current[key] = value
    if current:
        blocks.append(current)

    def pick(block: dict) -> tuple[str | None, str | None]:
        ssid = block.get("SSID") or None
        bssid = next((normalize_mac(v) for k, v in block.items() if k.upper().endswith("BSSID")), None)
        return ssid, bssid

    connected = [b for b in blocks if b.get("SSID")]
    if iface_mac:
        for block in connected:
            if any(normalize_mac(v) == iface_mac for v in block.values() if re.fullmatch(_MAC, v)):
                return pick(block)
    if len(connected) == 1:
        return pick(connected[0])
    return None, None


def wlan_ssid(iface_mac: str | None) -> tuple[str | None, str | None]:
    """SSID and BSSID of the Wi-Fi adapter, or (None, None) for Ethernet.

    Windows 11 hides these from ``netsh`` unless Location services are on for
    desktop apps; then both are None and matching uses the router alone.
    """
    if sys.platform != "win32":
        return None, None
    return parse_wlan_interfaces(_run(["netsh", "wlan", "show", "interfaces"]), iface_mac)


def current_fingerprint(iface: str) -> Fingerprint | None:
    """The network ``iface`` is on now, or None when it has no IPv4 address."""
    from ..utils.network_utils import default_gateway_ip, interface_info

    info = interface_info(iface)
    if info is None:
        return None
    gateway = default_gateway_ip(refresh=True)
    if gateway and ip_address(gateway) not in info.network:
        gateway = None
    gateway_mac = arp_cache_mac(gateway, info.ip) if gateway else None
    ssid, bssid = wlan_ssid(info.mac)
    return Fingerprint(str(info.network), info.ip, gateway, gateway_mac, ssid, bssid)


# ── Registry ─────────────────────────────────────────────────────────────────

@dataclass
class Network:
    id: str
    subnet: str
    first_seen: str
    last_seen: str
    gateway_ip: str | None = None
    gateway_macs: list[str] = field(default_factory=list)
    ssid: str | None = None
    bssids: list[str] = field(default_factory=list)
    label: str | None = None
    trust: str = DEFAULT_TRUST
    similar_to: str | None = None    # a known network with the same SSID and subnet but another router

    def to_api(self, current: bool = False) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "ssid": self.ssid,
            "subnet": self.subnet,
            "gateway_ip": self.gateway_ip,
            "gateway_mac": self.gateway_macs[0] if self.gateway_macs else None,
            "trust": self.trust,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "similar_to": self.similar_to,
            "current": current,
        }

    @property
    def display_name(self) -> str:
        return self.label or self.ssid or self.subnet


def validate_changes(label=_UNSET, trust=_UNSET) -> dict:
    """Normalise a label/trust update. Raises ValueError with a user-facing message."""
    changes = {}
    if label is not _UNSET:
        if label is not None and not isinstance(label, str):
            raise ValueError("label must be a string or null.")
        label = (label or "").strip() or None
        if label and len(label) > LABEL_MAX:
            raise ValueError(f"label must be at most {LABEL_MAX} characters.")
        changes["label"] = label
    if trust is not _UNSET:
        if trust not in TRUST_LEVELS:
            raise ValueError(f"trust must be one of {', '.join(TRUST_LEVELS)}.")
        changes["trust"] = trust
    return changes


class NetworkRegistry:
    """The index of known networks (``networks.json``) and their folders."""

    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "networks.json"
        self.folder = root / "networks"
        self._lock = threading.Lock()
        self._networks: dict[str, Network] = {}
        self._meta: dict[str, str] = {}
        self._listeners: list[Callable[[Network], None]] = []
        self._load()

    # ── Persistence ──────────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            known = {f for f in Network.__dataclass_fields__}
            for item in raw.get("networks", []):
                network = Network(**{k: v for k, v in item.items() if k in known})
                if network.trust not in TRUST_LEVELS:
                    network.trust = DEFAULT_TRUST
                self._networks[network.id] = network
            self._meta = {str(k): str(v) for k, v in raw.get("meta", {}).items()}
        except (OSError, ValueError, TypeError) as e:
            # Don't silently start over: the per-network databases are still there.
            backup = self.path.with_name(self.path.name + ".bad")
            log.error("Unreadable %s (%s); moved aside to %s", self.path, e, backup.name)
            self.path.replace(backup)
            self._networks, self._meta = {}, {}

    def _save(self) -> None:
        payload = {"version": 1, "meta": self._meta,
                   "networks": [asdict(n) for n in self._networks.values()]}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    # ── Queries ──────────────────────────────────────────────────────────────

    def get(self, network_id: str) -> Network | None:
        with self._lock:
            network = self._networks.get(network_id)
            return replace(network) if network else None

    def list(self) -> list[Network]:
        with self._lock:
            networks = [replace(n) for n in self._networks.values()]
        return sorted(networks, key=lambda n: n.last_seen, reverse=True)

    def db_path(self, network_id: str) -> Path:
        folder = self.folder / network_id
        folder.mkdir(parents=True, exist_ok=True)
        return folder / "devices.db"

    def get_meta(self, key: str) -> str | None:
        with self._lock:
            return self._meta.get(key)

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self._meta[key] = value
            self._save()

    def subscribe(self, fn: Callable[[Network], None]) -> None:
        with self._lock:
            self._listeners.append(fn)

    # ── Changes ──────────────────────────────────────────────────────────────

    def resolve(self, fp: Fingerprint, now: str | None = None) -> tuple[Network, bool]:
        """The known network ``fp`` belongs to, or a new idle one. Returns (network, created)."""
        now = now or iso(utcnow())
        with self._lock:
            network = self._networks.get(fp.id) or next(
                (n for n in self._networks.values()
                 if fp.gateway_mac and fp.gateway_mac in n.gateway_macs and n.subnet == fp.subnet), None)
            if network is None and fp.gateway_mac:
                # Seen before without its router's MAC (it wasn't in the ARP cache yet).
                network = next((n for n in self._networks.values()
                                if not n.gateway_macs and n.subnet == fp.subnet and n.ssid == fp.ssid), None)
            created = network is None
            if created:
                similar = self._lookalike(fp)
                network = Network(id=fp.id, subnet=fp.subnet, first_seen=now, last_seen=now,
                                  similar_to=similar.id if similar else None)
                self._networks[network.id] = network
            network.last_seen = now
            network.gateway_ip = fp.gateway_ip or network.gateway_ip
            if fp.gateway_mac and fp.gateway_mac not in network.gateway_macs:
                network.gateway_macs.append(fp.gateway_mac)
            network.ssid = fp.ssid or network.ssid
            if fp.bssid and fp.bssid not in network.bssids:
                network.bssids = (network.bssids + [fp.bssid])[-MAX_BSSIDS:]
            self._save()
            return replace(network), created

    def _lookalike(self, fp: Fingerprint) -> Network | None:
        """A known network with the same SSID and subnet but a different router."""
        if not fp.ssid:
            return None
        matches = [n for n in self._networks.values() if n.ssid == fp.ssid and n.subnet == fp.subnet]
        matches.sort(key=lambda n: (n.trust != "home", n.first_seen))
        return matches[0] if matches else None

    def update(self, network_id: str, label=_UNSET, trust=_UNSET) -> Network | None:
        changes = validate_changes(label, trust)
        with self._lock:
            network = self._networks.get(network_id)
            if network is None:
                return None
            for key, value in changes.items():
                setattr(network, key, value)
            self._save()
            result = replace(network)
            listeners = list(self._listeners)
        for fn in listeners:
            try:
                fn(result)
            except Exception:
                log.exception("Network listener failed")
        return result

    def forget(self, network_id: str) -> bool:
        """Remove a network and delete its inventory folder."""
        with self._lock:
            if self._networks.pop(network_id, None) is None:
                return False
            self._save()
        shutil.rmtree(self.folder / network_id, ignore_errors=True)
        return True

    # ── The pre-profiles database: adopted only when the user says so ─────────

    def legacy_info(self, network_id: str, legacy_db: Path) -> dict:
        """What the dashboard needs to offer the old device list on this network.

        ``likely_here`` is a hint, never a decision: it's true when the first
        router the old list recorded is this network's router. Networks can look
        identical except for that router (same subnet, router at .1), so the
        user always confirms.
        """
        available = not self._meta.get("legacy_adopted") and legacy_db.exists()
        info = {"available": bool(available), "devices": 0, "last_seen": None,
                "likely_here": False, "adoptable": False}
        if not available:
            return info
        network = self.get(network_id)
        info.update(legacy_summary(legacy_db))
        info["likely_here"] = bool(network and belongs_to(legacy_db, network))
        target = self.folder / network_id / "devices.db"
        info["adoptable"] = network is not None and (not target.exists() or _is_empty(target))
        return info

    def request_adoption(self, network_id: str, trust: str) -> None:
        """Remember to adopt the old list into ``network_id`` on the next start."""
        validate_changes(trust=trust)
        with self._lock:
            self._meta["pending_adoption"] = f"{network_id}:{trust}"
            self._save()

    def take_pending_adoption(self, network_id: str) -> str | None:
        """The trust level to adopt with, if adoption into ``network_id`` was requested."""
        with self._lock:
            pending = self._meta.get("pending_adoption", "")
            if not pending:
                return None
            del self._meta["pending_adoption"]
            self._save()
        target, _, trust = pending.partition(":")
        return trust if target == network_id and trust in TRUST_LEVELS else None

    def adopt_legacy(self, network_id: str, legacy_db: Path, trust: str = "home") -> bool:
        """Move the old single ``devices.db`` into ``network_id``. Only on the user's say-so.

        Refuses if it was adopted already, or if this network has recorded
        anything of its own (its inventory is never overwritten).
        """
        if self._meta.get("legacy_adopted") or not legacy_db.exists():
            return False
        with self._lock:
            network = self._networks.get(network_id)
        if network is None:
            return False
        target = self.db_path(network_id)
        if target.exists():
            if not _is_empty(target):
                log.warning("Not adopting %s: %s already holds devices or events", legacy_db, target)
                return False
            for suffix in ("", "-wal", "-shm"):
                target.with_name(target.name + suffix).unlink(missing_ok=True)
        for suffix in ("", "-wal", "-shm"):
            source = legacy_db.with_name(legacy_db.name + suffix)
            if source.exists():
                os.replace(source, target.with_name(target.name + suffix))
        with self._lock:
            network.trust = trust
            self._meta["legacy_adopted"] = network_id
            self._save()
        log.info("Adopted the existing device list into network %s (%s)", network_id, trust)
        return True


# ── Reset: wipe every device list, applied at the next start ───────────────

RESET_MARKER = "reset-pending"
# Everything that holds devices or history. Settings (config.toml, tray.json) and logs are kept.
_RESET_FILES = ("networks.json", "networks.json.bad", "networks.tmp",
                "devices.db", "devices.db-wal", "devices.db-shm")
_RESET_FOLDERS = ("networks", "replay")


def request_reset(root: Path) -> None:
    """Ask for every device list to be deleted when NetSleuth next starts.

    It can't happen while running: the current network's database is open.
    """
    (root / RESET_MARKER).write_text(iso(utcnow()), encoding="utf-8")


def apply_pending_reset(root: Path) -> bool:
    """If a reset was requested, delete all device data now (before anything opens it)."""
    marker = root / RESET_MARKER
    if not marker.exists():
        return False
    for name in _RESET_FOLDERS:
        shutil.rmtree(root / name, ignore_errors=True)
    for name in _RESET_FILES:
        (root / name).unlink(missing_ok=True)
    marker.unlink(missing_ok=True)
    log.warning("Reset: deleted every network and device list in %s (settings and logs kept)", root)
    return True


def legacy_summary(legacy_db: Path) -> dict:
    """Device count and most recent sighting in the old database."""
    try:
        conn = sqlite3.connect(f"file:{legacy_db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return {}
    try:
        count, last_seen = conn.execute("SELECT COUNT(*), MAX(last_seen) FROM devices").fetchone()
        return {"devices": count or 0, "last_seen": last_seen}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def belongs_to(legacy_db: Path, network: Network) -> bool:
    """Is ``legacy_db`` the inventory of ``network``?

    Yes only if the first router it recorded is this network's router. Later
    routers are networks the PC visited, even at the same address on the same
    subnet: many ISPs hand out 10.0.0.0/24 or 192.168.1.0/24 with the router at
    .1, so a friend's network can look identical except for the router's MAC.
    A genuinely replaced router is linked by the user, never guessed. Without
    any recorded router, yes if most addresses are in this subnet.
    """
    try:
        conn = sqlite3.connect(f"file:{legacy_db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        subnet = ip_network(network.subnet)
        try:
            rows = conn.execute("SELECT mac FROM devices WHERE is_gateway = 1 ORDER BY first_seen, rowid").fetchall()
        except sqlite3.OperationalError:     # schema v1 had no is_gateway column
            rows = []
        if rows:
            return rows[0][0] in network.gateway_macs
        ips = [r[0] for r in conn.execute("SELECT ip FROM device_ips").fetchall()]
        inside = sum(1 for ip in ips if _in(ip, subnet))
        return bool(ips) and inside * 2 > len(ips)
    except sqlite3.Error as e:
        log.warning("Can't read %s: %s", legacy_db, e)
        return False
    finally:
        conn.close()


def _is_empty(db: Path) -> bool:
    """True if ``db`` has no devices and no events. Unreadable counts as not empty."""
    try:
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return False
    try:
        devices = conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0]
        events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        return devices == 0 and events == 0
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def _in(ip: str, subnet) -> bool:
    try:
        return ip_address(ip) in subnet
    except ValueError:
        return False


# ── Watching for a move to another network ───────────────────────────────────

class NetworkWatch:
    """Notices when this PC moves to another network (or changes address).

    ``on_link(False)`` while the interface has no IPv4 address (disconnected,
    asleep); ``on_change(fp)`` once, when it's positively on another network.
    """

    def __init__(
        self,
        iface: str,
        start: Fingerprint,
        on_change: Callable[[Fingerprint], None],
        on_link: Callable[[bool], None] = lambda up: None,
        interval_s: float = WATCH_INTERVAL_S,
        read: Callable[[str], Fingerprint | None] = current_fingerprint,
    ):
        self._iface = iface
        self._start = start
        self._on_change = on_change
        self._on_link = on_link
        self._interval_s = interval_s
        self._read = read
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def check(self) -> bool:
        """One check. Returns True once the network has changed."""
        fp = self._read(self._iface)
        if fp is None:
            self._on_link(False)
            return False
        self._on_link(True)
        if self._start.same_network(fp):
            return False
        log.info("Network changed: %s via %s -> %s via %s",
                 self._start.subnet, self._start.gateway_mac, fp.subnet, fp.gateway_mac)
        self._on_change(fp)
        return True

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="network-watch", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while not self._stop.wait(self._interval_s):
            try:
                if self.check():
                    return
            except Exception:
                log.exception("Network check failed")
