"""Tray preferences: which interface to watch, which port, notifications."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from .paths import data_dir

log = logging.getLogger(__name__)


@dataclass
class TrayConfig:
    interface: str | None = None
    port: int = 5000
    notifications: bool = True

    @staticmethod
    def path() -> Path:
        return data_dir() / "tray.json"

    @classmethod
    def load(cls) -> "TrayConfig":
        try:
            raw = json.loads(cls.path().read_text(encoding="utf-8"))
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as e:
            log.warning("Ignoring unreadable %s: %s", cls.path(), e)
            return cls()
        config = cls()
        types = {f.name: f.type for f in fields(cls)}
        for key, value in raw.items() if isinstance(raw, dict) else []:
            if key == "interface" and (value is None or isinstance(value, str)):
                config.interface = value
            elif key == "port" and isinstance(value, int) and not isinstance(value, bool) and 1024 <= value <= 65535:
                config.port = value
            elif key == "notifications" and isinstance(value, bool):
                config.notifications = value
            elif key not in types:
                log.warning("Ignoring unknown tray setting %r", key)
        return config

    def save(self) -> None:
        path = self.path()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        tmp.replace(path)
