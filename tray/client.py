"""Minimal client for the backend's v1 API (docs/API_CONTRACT.md)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class BackendUnavailable(Exception):
    pass


class BackendClient:
    def __init__(self, port: int, timeout: float = 3.0):
        self.base = f"http://127.0.0.1:{port}/api/v1"
        self.timeout = timeout

    def _request(self, method: str, path: str) -> Any:
        data = b"{}" if method != "GET" else None
        req = urllib.request.Request(
            self.base + path, data=data, method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read() or b"null")
        except (urllib.error.URLError, OSError, ValueError) as e:
            raise BackendUnavailable(str(e)) from e

    def health(self) -> dict:
        return self._request("GET", "/health")

    def summary(self) -> dict:
        return self._request("GET", "/summary")

    def events(self, since: int | None = None, limit: int = 50) -> list[dict]:
        query = f"?limit={limit}" + (f"&since={since}" if since is not None else "")
        return self._request("GET", f"/events{query}")

    def pause(self) -> dict:
        return self._request("POST", "/capture/pause")

    def resume(self) -> dict:
        return self._request("POST", "/capture/resume")


def is_notable(event: dict) -> bool:
    """Events worth a desktop notification (matches the web UI's rule)."""
    kind, severity = event.get("kind"), event.get("severity")
    if kind == "new_device":
        return (event.get("data") or {}).get("baseline") is not True
    if kind == "mac_conflict":
        return True
    return kind == "alert" and severity in ("high", "critical")
