"""User-tunable settings and on-disk locations.

Settings live in ``<data_dir>/config.toml``. Any key can be overridden for a
single run with an environment variable ``NETSLEUTH_<KEY>`` (e.g.
``NETSLEUTH_SWEEP_INTERVAL_S=60``). ``NETSLEUTH_HOME`` relocates the whole
data directory.
"""
from __future__ import annotations

import logging
import os
import sys
import tomllib
from dataclasses import asdict, dataclass, fields
from pathlib import Path

log = logging.getLogger(__name__)


# ── Locations ────────────────────────────────────────────────────────────────

def data_dir() -> Path:
    override = os.environ.get("NETSLEUTH_HOME")
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "NetSleuth"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "netsleuth"
    base.mkdir(parents=True, exist_ok=True)
    return base


def config_path() -> Path:
    return data_dir() / "config.toml"


def db_path() -> Path:
    return data_dir() / "devices.db"


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(exist_ok=True)
    return path


# ── Settings ─────────────────────────────────────────────────────────────────

# (min, max) for numeric settings; values outside are rejected.
_BOUNDS = {
    "offline_timeout_s": (60, 86_400),
    "sweep_interval_s": (30, 86_400),
    "retention_days": (1, 3_650),
    "identify_minutes": (5, 30),
}


@dataclass
class Settings:
    offline_timeout_s: int = 600     # device marked offline after this much silence
    sweep_interval_s: int = 300      # ARP sweep cadence
    retention_days: int = 30         # events / traffic counts older than this are pruned
    lan_exposure: bool = False       # bind dashboard to 0.0.0.0 (takes effect on restart)
    anomaly_plugin: bool = False     # optional ML anomaly detection
    port_check: bool = False         # Identify mode may also check 13 common ports per device
    identify_minutes: int = 10       # how long an Identify run may take before it switches off

    def update(self, changes: dict) -> None:
        """Validate and apply a partial update. Raises ValueError on bad input."""
        valid = {f.name: f.type for f in fields(self)}
        unknown = set(changes) - set(valid)
        if unknown:
            raise ValueError(f"unknown setting(s): {', '.join(sorted(unknown))}")

        staged = {}
        for key, value in changes.items():
            if valid[key] == "bool":
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be a boolean")
            else:
                if isinstance(value, bool) or not isinstance(value, int):
                    raise ValueError(f"{key} must be an integer")
                lo, hi = _BOUNDS[key]
                if not lo <= value <= hi:
                    raise ValueError(f"{key} must be between {lo} and {hi}")
            staged[key] = value

        for key, value in staged.items():
            setattr(self, key, value)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or config_path()
        settings = cls()

        if path.exists():
            try:
                with path.open("rb") as fh:
                    settings.update(tomllib.load(fh))
            except (tomllib.TOMLDecodeError, ValueError) as e:
                log.warning("Ignoring invalid config %s: %s", path, e)

        for f in fields(settings):
            raw = os.environ.get(f"NETSLEUTH_{f.name.upper()}")
            if raw is None:
                continue
            try:
                value = raw.strip().lower() in ("1", "true", "yes", "on") if f.type == "bool" else int(raw)
                settings.update({f.name: value})
            except ValueError as e:
                log.warning("Ignoring env override NETSLEUTH_%s: %s", f.name.upper(), e)

        return settings

    def save(self, path: Path | None = None) -> None:
        path = path or config_path()
        lines = [
            f"{key} = {str(value).lower() if isinstance(value, bool) else value}"
            for key, value in self.to_dict().items()
        ]
        tmp = path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(path)
