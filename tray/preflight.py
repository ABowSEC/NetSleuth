"""Checks before starting, the single-instance lock, and user-facing messages."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


class PreflightError(Exception):
    """Something the user has to fix before NetSleuth can run."""


def check_backend_installed() -> None:
    if importlib.util.find_spec("netsleuth") is None:
        raise PreflightError(
            "NetSleuth's backend isn't installed for this Python.\n\nRun setup.bat in the NetSleuth folder, then try again."
        )


def npcap_installed() -> bool:
    if sys.platform != "win32":
        return True
    system32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
    return (system32 / "Npcap" / "wpcap.dll").exists()


def check_npcap() -> None:
    if not npcap_installed():
        raise PreflightError(
            "Npcap isn't installed. NetSleuth needs it to see devices on your network.\n\n"
            "Download it from https://npcap.com, install with the default options, then start NetSleuth again."
        )


class AlreadyRunning(Exception):
    pass


class SingleInstance:
    """Holds an exclusive lock on run/tray.lock for the life of the process."""

    def __init__(self, run_dir: Path):
        self._file = (run_dir / "tray.lock").open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt
                self._file.seek(0)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            self._file.close()
            raise AlreadyRunning() from e

    def release(self) -> None:
        if not self._file.closed:
            self._file.close()


def show_message(title: str, text: str, error: bool = True) -> None:
    """A native message box on Windows (the tray has no console), else stderr."""
    if sys.platform == "win32":
        import ctypes
        flags = 0x10 if error else 0x40  # MB_ICONERROR / MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(None, text, title, flags)
    else:
        print(f"{title}: {text}", file=sys.stderr)
