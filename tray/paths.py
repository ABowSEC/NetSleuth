"""Where the tray keeps its files.

Uses the same data directory as the backend (NETSLEUTH_HOME, else
%LOCALAPPDATA%\\NetSleuth), but doesn't import the backend: the tray only
depends on the backend's command line and HTTP API.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


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


def run_dir() -> Path:
    path = data_dir() / "run"
    path.mkdir(exist_ok=True)
    return path


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(exist_ok=True)
    return path


def ui_index() -> Path:
    return REPO_ROOT / "frontend" / "out" / "index.html"
