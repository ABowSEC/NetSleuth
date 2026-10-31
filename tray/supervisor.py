"""Runs the NetSleuth backend as a child process and keeps it alive.

Lifecycle
- start(): reap a stale backend left by a crashed tray (PID file), spawn,
  wait for GET /api/v1/health, then watch the process.
- Unexpected exit: restart with backoff; give up after ``max_crashes``
  within ``crash_window`` seconds. Exit codes 2, 3 and 4 are configuration
  problems (bad interface, capture not permitted, port taken) and are never
  retried: restarting can't fix them.
- stop(): close the child's stdin (it was started with --exit-on-stdin-close)
  so it shuts down cleanly; kill the whole process tree if it hasn't exited
  within ``stop_grace`` seconds.
"""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import threading
import time
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Callable

import psutil

log = logging.getLogger(__name__)

STDERR_LOG_MAX = 1_000_000


class State(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    RESTARTING = "restarting"
    ERROR = "error"


def exit_message(code: int, port: int) -> str | None:
    """Human explanation for the backend's documented exit codes."""
    return {
        2: "NetSleuth couldn't use the selected network interface. Pick another one from the Network interface menu.",
        3: "Windows refused packet capture. Npcap may be installed in admin-only mode: reinstall it without "
           "\"Restrict Npcap driver's access to Administrators only\", or run NetSleuth as administrator.",
        4: f"Port {port} is already in use by another program. Close it, or change the port in tray.json.",
    }.get(code)


def kill_tree(pid: int, timeout: float = 3.0) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return
    procs = parent.children(recursive=True) + [parent]
    for proc in procs:
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(procs, timeout=timeout)


class Supervisor:
    def __init__(
        self,
        command: Callable[[], list[str]],
        port: int,
        run_dir: Path,
        log_dir: Path,
        on_change: Callable[[State, str], None] = lambda state, message: None,
        health_timeout: float = 30.0,
        stop_grace: float = 8.0,
        backoff: tuple[float, ...] = (2, 4, 8, 16, 32),
        max_crashes: int = 5,
        crash_window: float = 600.0,
    ):
        self._command = command
        self.port = port
        self._pid_file = run_dir / "backend.pid"
        self._stderr_log = log_dir / "backend-stderr.log"
        self._on_change = on_change
        self._health_timeout = health_timeout
        self._stop_grace = stop_grace
        self._backoff = backoff
        self._max_crashes = max_crashes
        self._crash_window = crash_window

        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen | None = None
        self.state = State.STOPPED
        self.message = ""

    # ── Public ───────────────────────────────────────────────────────────────

    def start(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="supervisor", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            self._shutdown(proc)
        if self._thread:
            self._thread.join(timeout=self._stop_grace + 5)
        self._set(State.STOPPED, "")

    def restart(self) -> None:
        self.stop()
        self.start()

    @property
    def pid(self) -> int | None:
        with self._lock:
            return self._proc.pid if self._proc and self._proc.poll() is None else None

    # ── Internals ────────────────────────────────────────────────────────────

    def _set(self, state: State, message: str) -> None:
        self.state, self.message = state, message
        try:
            self._on_change(state, message)
        except Exception:
            log.exception("State listener failed")

    def _run(self) -> None:
        crashes: list[float] = []
        while not self._stop.is_set():
            self._reap_stale()
            self._set(State.STARTING, "Starting NetSleuth…")
            proc = self._spawn()
            if proc is None:
                self._set(State.ERROR, "Couldn't start the NetSleuth backend. See backend-stderr.log in the logs folder.")
                return

            if self._wait_healthy(proc):
                self._set(State.RUNNING, "")
                code = proc.wait()
            elif proc.poll() is None:
                log.warning("Backend didn't answer within %.0fs; killing it", self._health_timeout)
                kill_tree(proc.pid)
                code = proc.wait()
            else:
                code = proc.returncode

            self._clear_pid_file()
            with self._lock:
                self._proc = None
            if self._stop.is_set():
                return

            log.warning("Backend exited with code %s", code)
            fatal = exit_message(code, self.port)
            if fatal:
                self._set(State.ERROR, fatal)
                return

            now = time.monotonic()
            crashes = [t for t in crashes if now - t < self._crash_window] + [now]
            if len(crashes) >= self._max_crashes:
                self._set(State.ERROR, f"NetSleuth stopped unexpectedly {len(crashes)} times in a row. "
                                       "Check backend.log in the logs folder, then choose Restart.")
                return
            delay = self._backoff[min(len(crashes), len(self._backoff)) - 1]
            self._set(State.RESTARTING, f"NetSleuth stopped unexpectedly (exit code {code}). Restarting in {delay:g}s.")
            if self._stop.wait(delay):
                return

    def _spawn(self) -> subprocess.Popen | None:
        if self._stderr_log.exists() and self._stderr_log.stat().st_size > STDERR_LOG_MAX:
            self._stderr_log.replace(self._stderr_log.with_suffix(".log.1"))
        flags = 0
        if sys.platform == "win32":
            flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
        command = self._command()
        log.info("Starting backend: %s", " ".join(command))
        try:
            with self._stderr_log.open("ab") as stderr:
                proc = subprocess.Popen(
                    command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr,
                    creationflags=flags, close_fds=True,
                )
        except OSError:
            log.exception("Failed to start backend")
            return None
        with self._lock:
            self._proc = proc
        self._write_pid_file(proc.pid)
        return proc

    def _wait_healthy(self, proc: subprocess.Popen) -> bool:
        url = f"http://127.0.0.1:{self.port}/api/v1/health"
        deadline = time.monotonic() + self._health_timeout
        while time.monotonic() < deadline and not self._stop.is_set():
            if proc.poll() is not None:
                return False
            try:
                with urllib.request.urlopen(url, timeout=1) as resp:
                    if resp.status == 200:
                        return True
            except OSError:
                pass
            self._stop.wait(0.25)
        return False

    def _shutdown(self, proc: subprocess.Popen) -> None:
        try:
            if proc.stdin:
                proc.stdin.close()   # backend sees EOF and exits cleanly
        except OSError:
            pass
        try:
            proc.wait(timeout=self._stop_grace)
            log.info("Backend stopped cleanly")
        except subprocess.TimeoutExpired:
            log.warning("Backend didn't stop within %.0fs; killing it", self._stop_grace)
            kill_tree(proc.pid)

    # ── PID file ─────────────────────────────────────────────────────────────

    def _write_pid_file(self, pid: int) -> None:
        try:
            created = psutil.Process(pid).create_time()
        except psutil.NoSuchProcess:
            return
        self._pid_file.write_text(json.dumps({"pid": pid, "create_time": created}), encoding="utf-8")

    def _clear_pid_file(self) -> None:
        self._pid_file.unlink(missing_ok=True)

    def _reap_stale(self) -> None:
        """Kill a backend left running by a previous tray that crashed."""
        try:
            info = json.loads(self._pid_file.read_text(encoding="utf-8"))
            pid, created = int(info["pid"]), float(info["create_time"])
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError):
            self._clear_pid_file()
            return
        try:
            proc = psutil.Process(pid)
            # PIDs get reused: only kill the exact process we started.
            if abs(proc.create_time() - created) < 1.0:
                log.warning("Stopping stale backend from a previous session (pid %d)", pid)
                kill_tree(pid)
        except psutil.NoSuchProcess:
            pass
        self._clear_pid_file()
