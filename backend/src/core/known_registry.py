import json
import os
from typing import Optional

REGISTRY_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "known_devices.json")


def _load() -> dict:
    try:
        with open(REGISTRY_PATH) as f:
            data = json.load(f)
            if "mac" not in data:
                data["mac"] = {}
            return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {"mac": {}}


def _save(data: dict) -> None:
    with open(REGISTRY_PATH, "w") as f:
        json.dump(data, f, indent=2)


def is_known(mac: Optional[str]) -> bool:
    if not mac or mac == "Unknown":
        return False
    return mac.lower() in _load()["mac"]


def get_name(mac: Optional[str]) -> Optional[str]:
    if not mac or mac == "Unknown":
        return None
    return _load()["mac"].get(mac.lower(), {}).get("name")


def claim(mac: Optional[str], ip: str, name: str) -> None:
    """Register a device as known with a friendly name."""
    data = _load()
    key = mac.lower() if mac and mac != "Unknown" else ip
    data["mac"][key] = {"name": name}
    _save(data)


def unclaim(mac: Optional[str], ip: str) -> None:
    """Remove a device from the known registry."""
    data = _load()
    key = mac.lower() if mac and mac != "Unknown" else ip
    data["mac"].pop(key, None)
    _save(data)


def all_known() -> dict:
    return _load()["mac"]
