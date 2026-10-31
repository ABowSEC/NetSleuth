"""The system-tray icon: status, quick actions, and new-device notifications."""
from __future__ import annotations

import logging
import os
import sys
import threading
import webbrowser
from logging.handlers import RotatingFileHandler

from . import autostart, netinfo
from .client import BackendClient, BackendUnavailable, is_notable
from .config import TrayConfig
from .paths import log_dir, run_dir, ui_index
from .preflight import AlreadyRunning, PreflightError, SingleInstance, check_backend_installed, check_npcap, show_message
from .supervisor import State, Supervisor

log = logging.getLogger("netsleuth.tray")

POLL_S = 10
TITLE = "NetSleuth"

# Matches the web UI: green here, amber attention, red trouble, grey stopped.
COLORS = {
    "running": (26, 127, 55),
    "attention": (168, 90, 0),
    "error": (194, 50, 27),
    "stopped": (109, 105, 97),
}


def make_icon(color: tuple[int, int, int]):
    """A 64px rounded square in ``color`` with a white magnifying glass."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((2, 2, 62, 62), radius=14, fill=(*color, 255))
    draw.ellipse((13, 13, 41, 41), outline="white", width=6)
    draw.line((37, 37, 51, 51), fill="white", width=7)
    return img


def backend_python() -> str:
    """python.exe next to us (std handles always valid), even if the tray runs under pythonw."""
    exe = os.path.dirname(sys.executable)
    candidate = os.path.join(exe, "python.exe")
    return candidate if os.path.exists(candidate) else sys.executable


class TrayApp:
    def __init__(self, config: TrayConfig):
        self.config = config
        self.client = BackendClient(config.port)
        self.status = "Starting…"
        self.paused = False
        self._last_event_id: int | None = None
        self._stop = threading.Event()
        self._icon = None
        self.supervisor = Supervisor(
            command=self._command, port=config.port, run_dir=run_dir(), log_dir=log_dir(),
            on_change=self._on_state,
        )

    # ── Backend ──────────────────────────────────────────────────────────────

    def _command(self) -> list[str]:
        return [
            backend_python(), "-m", "netsleuth",
            "--headless", "--exit-on-stdin-close",
            "--interface", self.config.interface or "",
            "--port", str(self.config.port),
            "--log-file", str(log_dir() / "backend.log"),
        ]

    def _on_state(self, state: State, message: str) -> None:
        if state == State.RUNNING:
            self._last_event_id = None
            self._refresh()
            return
        self.status = {
            State.STARTING: "Starting…",
            State.STOPPED: "Stopped",
        }.get(state, message)
        self._draw("attention" if state in (State.STARTING, State.RESTARTING) else
                   "error" if state == State.ERROR else "stopped")
        if state == State.ERROR:
            self._notify(message)

    def _refresh(self) -> None:
        """Pull status and new events from the backend (runs every POLL_S)."""
        if self.supervisor.state != State.RUNNING:
            return
        try:
            health = self.client.health()
            summary = self.client.summary()
            self.paused = not health.get("capturing", True)
            here, unknown = summary.get("online", 0), summary.get("unknown", 0)
            self.status = "Paused" if self.paused else (
                f"{here} here now" + (f" · {unknown} not recognised" if unknown else "")
            )
            self._draw("attention" if self.paused or unknown else "running")
            self._check_events()
        except BackendUnavailable:
            self.status = "Waiting for NetSleuth…"
            self._draw("attention")

    def _check_events(self) -> None:
        if self._last_event_id is None:
            latest = self.client.events(limit=1)
            self._last_event_id = latest[0]["id"] if latest else 0
            return  # don't replay history as notifications
        fresh = self.client.events(since=self._last_event_id, limit=20)
        if not fresh:
            return
        self._last_event_id = max(e.get("id", 0) for e in fresh)
        if self.config.notifications:
            for event in reversed(fresh):
                if is_notable(event):
                    self._notify(event.get("message", ""))

    def _poll_loop(self) -> None:
        while not self._stop.wait(POLL_S):
            try:
                self._refresh()
            except Exception:
                log.exception("Status refresh failed")

    # ── Icon ─────────────────────────────────────────────────────────────────

    def _draw(self, tone: str) -> None:
        if self._icon:
            self._icon.icon = make_icon(COLORS[tone])
            self._icon.title = f"{TITLE}: {self.status}"
            self._icon.update_menu()

    def _notify(self, message: str) -> None:
        if self._icon and message:
            try:
                self._icon.notify(message, TITLE)
            except Exception:
                log.exception("Notification failed")

    def _menu(self):
        from pystray import Menu, MenuItem as Item

        running = lambda item: self.supervisor.state == State.RUNNING  # noqa: E731

        def interfaces():
            for name, ip in netinfo.candidate_interfaces():
                yield Item(f"{name} ({ip})", self._choose_interface(name),
                           checked=lambda item, n=name: self.config.interface == n, radio=True)

        return Menu(
            Item(lambda item: self.status, None, enabled=False),
            Menu.SEPARATOR,
            Item("Open dashboard", self._open_dashboard, default=True),
            Item(lambda item: "Resume monitoring" if self.paused else "Pause monitoring", self._toggle_pause,
                 enabled=running),
            Item("Network interface", Menu(interfaces)),
            Item("Notify me about new devices", self._toggle_notifications,
                 checked=lambda item: self.config.notifications),
            Item("Start with Windows", self._toggle_autostart,
                 checked=lambda item: autostart.is_enabled(), visible=autostart.supported()),
            Item("Open logs folder", self._open_logs),
            Menu.SEPARATOR,
            Item("Restart NetSleuth", self._restart),
            Item("Quit", self._quit),
        )

    # ── Actions ──────────────────────────────────────────────────────────────

    def _open_dashboard(self, icon=None, item=None) -> None:
        webbrowser.open(f"http://localhost:{self.config.port}/")

    def _toggle_pause(self, icon=None, item=None) -> None:
        try:
            health = self.client.resume() if self.paused else self.client.pause()
            self.paused = not health.get("capturing", True)
        except BackendUnavailable:
            self._notify("Couldn't reach NetSleuth to change monitoring.")
        self._refresh()

    def _choose_interface(self, name: str):
        def choose(icon=None, item=None) -> None:
            if name == self.config.interface:
                return
            self.config.interface = name
            self.config.save()
            log.info("Switching to interface %s", name)
            threading.Thread(target=self.supervisor.restart, daemon=True).start()
        return choose

    def _toggle_notifications(self, icon=None, item=None) -> None:
        self.config.notifications = not self.config.notifications
        self.config.save()

    def _toggle_autostart(self, icon=None, item=None) -> None:
        try:
            autostart.set_enabled(not autostart.is_enabled())
        except OSError:
            log.exception("Couldn't change the startup entry")
            self._notify("Couldn't change the Start with Windows setting.")

    def _open_logs(self, icon=None, item=None) -> None:
        path = str(log_dir())
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 - opening our own folder in Explorer
        else:
            webbrowser.open(f"file://{path}")

    def _restart(self, icon=None, item=None) -> None:
        threading.Thread(target=self.supervisor.restart, daemon=True).start()

    def _quit(self, icon=None, item=None) -> None:
        self._stop.set()
        self.status = "Stopping…"
        self.supervisor.stop()
        if self._icon:
            self._icon.stop()

    # ── Run ──────────────────────────────────────────────────────────────────

    def run(self) -> None:
        import pystray

        self._icon = pystray.Icon(TITLE, make_icon(COLORS["attention"]), TITLE, self._menu())

        def setup(icon) -> None:
            icon.visible = True
            if not ui_index().exists():
                self._notify("The dashboard isn't built yet, so only the API is available. Run setup.bat to build it.")
            self.supervisor.start()
            threading.Thread(target=self._poll_loop, name="tray-poll", daemon=True).start()

        self._icon.run(setup=setup)


def _configure_logging() -> None:
    handler = RotatingFileHandler(log_dir() / "tray.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def main() -> int:
    _configure_logging()
    try:
        check_backend_installed()
        check_npcap()
    except PreflightError as e:
        show_message(TITLE, str(e))
        return 1

    try:
        lock = SingleInstance(run_dir())
    except AlreadyRunning:
        show_message(TITLE, "NetSleuth is already running. Look for its icon in the notification area.", error=False)
        return 0

    try:
        config = TrayConfig.load()
        if not config.interface:
            candidates = netinfo.candidate_interfaces()
            config.interface = netinfo.default_interface(candidates, netinfo.internet_facing_ip())
            if not config.interface:
                show_message(TITLE, "No connected network was found. Connect to your home network and try again.")
                return 1
            config.save()
            log.info("Using interface %s", config.interface)
        TrayApp(config).run()
        return 0
    finally:
        lock.release()
