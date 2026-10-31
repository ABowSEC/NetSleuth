import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

from tray.paths import log_dir, run_dir
from tray.supervisor import State, Supervisor

FAKE = str(Path(__file__).with_name("fake_backend.py"))


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


class Harness:
    """A Supervisor wired to the fake backend, recording states and spawns."""

    def __init__(self, **kwargs):
        self.port = free_port()
        self.states: list[State] = []
        self.spawns = 0
        defaults = dict(health_timeout=10.0, stop_grace=5.0, backoff=(0.05,), max_crashes=3)
        self.sup = Supervisor(
            command=self._command, port=self.port, run_dir=run_dir(), log_dir=log_dir(),
            on_change=lambda state, message: self.states.append(state),
            **{**defaults, **kwargs},
        )

    def _command(self):
        self.spawns += 1
        return [sys.executable, FAKE, "--port", str(self.port)]


@pytest.fixture
def harness():
    created = []

    def make(**kwargs):
        h = Harness(**kwargs)
        created.append(h)
        return h

    yield make
    for h in created:
        h.sup.stop()


def test_start_then_clean_stop_via_stdin(harness, monkeypatch, tmp_path):
    marker = tmp_path / "marker"
    monkeypatch.setenv("FAKE_MODE", "ok")
    monkeypatch.setenv("FAKE_MARKER", str(marker))
    h = harness()
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.RUNNING)

    pid = h.sup.pid
    pid_file = run_dir() / "backend.pid"
    assert json.loads(pid_file.read_text())["pid"] == pid

    h.sup.stop()
    assert h.sup.state == State.STOPPED
    assert marker.read_text() == "clean"          # exited on its own, not killed
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert not pid_file.exists()


def test_crashes_restart_with_backoff_then_give_up(harness, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "die")
    h = harness(max_crashes=3)
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.ERROR, timeout=20)
    assert h.spawns == 3
    assert State.RESTARTING in h.states and State.RUNNING in h.states
    assert "3 times" in h.sup.message


@pytest.mark.parametrize("code, needle", [(3, "Npcap"), (4, "already in use"), (2, "interface")])
def test_configuration_errors_are_not_retried(harness, monkeypatch, code, needle):
    monkeypatch.setenv("FAKE_MODE", f"exit{code}")
    h = harness()
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.ERROR)
    time.sleep(0.3)
    assert h.spawns == 1
    assert needle in h.sup.message


def test_hung_backend_is_killed_on_stop(harness, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "hang")
    h = harness(stop_grace=0.5)
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.RUNNING)
    pid = h.sup.pid
    h.sup.stop()
    assert wait_for(lambda: not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE)


def test_backend_that_never_answers_counts_as_crash(harness, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "slow")
    monkeypatch.setenv("FAKE_DELAY", "30")
    h = harness(health_timeout=0.5, max_crashes=1)
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.ERROR, timeout=15)
    assert h.spawns == 1


def test_stale_backend_from_crashed_tray_is_reaped(harness, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "hang")
    stale = subprocess.Popen([sys.executable, FAKE, "--port", str(free_port())], stdin=subprocess.PIPE)
    try:
        (run_dir() / "backend.pid").write_text(json.dumps(
            {"pid": stale.pid, "create_time": psutil.Process(stale.pid).create_time()}))
        monkeypatch.setenv("FAKE_MODE", "ok")
        h = harness()
        h.sup.start()
        assert stale.wait(timeout=10) is not None
        assert wait_for(lambda: h.sup.state == State.RUNNING)
    finally:
        if stale.poll() is None:
            stale.kill()


def test_pid_file_for_a_reused_pid_is_ignored(harness, monkeypatch):
    # Our own PID with a wrong start time: must not be killed.
    (run_dir() / "backend.pid").write_text(json.dumps({"pid": psutil.Process().pid, "create_time": 1.0}))
    monkeypatch.setenv("FAKE_MODE", "ok")
    h = harness()
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.RUNNING)
    assert psutil.Process().is_running()


def test_corrupt_pid_file_is_removed(harness, monkeypatch):
    (run_dir() / "backend.pid").write_text("not json")
    monkeypatch.setenv("FAKE_MODE", "ok")
    h = harness()
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.RUNNING)
    assert json.loads((run_dir() / "backend.pid").read_text())["pid"] == h.sup.pid


def test_restart_spawns_a_new_process(harness, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "ok")
    h = harness()
    h.sup.start()
    assert wait_for(lambda: h.sup.state == State.RUNNING)
    first = h.sup.pid
    h.sup.restart()
    assert wait_for(lambda: h.sup.state == State.RUNNING and h.sup.pid not in (None, first))
    assert h.spawns == 2
