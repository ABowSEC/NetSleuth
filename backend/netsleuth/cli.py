"""Command-line entry point: ``python -m netsleuth``.

Exit codes follow docs/API_CONTRACT.md:
0 clean shutdown, 1 other error, 2 usage/config error,
3 capture permission denied, 4 port in use.
"""
from __future__ import annotations

import _thread
import argparse
import logging
import signal
import socket
import sys
import threading
from ipaddress import ip_address

from . import __version__
from .logging_setup import configure_logging
from .settings import Settings, log_dir

log = logging.getLogger("netsleuth")

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_PERMISSION = 3
EXIT_PORT_IN_USE = 4


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="netsleuth", description="NetSleuth home-network device tracker")
    parser.add_argument("--interface", "-i", help="network interface to monitor")
    parser.add_argument("--host", help="dashboard bind address (default 127.0.0.1, or 0.0.0.0 with LAN exposure)")
    parser.add_argument("--port", "-p", type=int, default=5000, help="dashboard port (default 5000)")
    parser.add_argument("--headless", action="store_true", help="never prompt; fail if a choice is needed")
    parser.add_argument("--dev", action="store_true", help="allow the Next.js dev server origin (localhost:3000)")
    parser.add_argument("--log-file", help="log file path (default <data dir>/logs/netsleuth.log)")
    parser.add_argument("--verbose", "-v", action="store_true", help="debug logging")
    parser.add_argument("--exit-on-stdin-close", action="store_true",
                        help="shut down cleanly when stdin closes (used by the tray supervisor)")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def port_in_use(host: str, port: int) -> bool:
    """True if something is already listening on host:port."""
    probe = "127.0.0.1" if host in ("0.0.0.0", "") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        if s.connect_ex((probe, port)) == 0:
            return True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
        except OSError:
            return True
    return False


def choose_interface(requested: str | None, available: list[str], headless: bool) -> str | None:
    if requested:
        if requested in available:
            return requested
        log.error("Interface %r not found. Available: %s", requested, ", ".join(available) or "none")
        return None
    if len(available) == 1:
        log.info("Auto-selecting interface: %s", available[0])
        return available[0]
    if not available:
        log.error("No active network interfaces found.")
        return None
    if headless:
        log.error("Multiple interfaces found; pass --interface. Available: %s", ", ".join(available))
        return None

    print("Multiple active interfaces found:")
    for idx, iface in enumerate(available, start=1):
        print(f"  {idx}. {iface}")
    try:
        return available[int(input("Select interface number: ")) - 1]
    except (IndexError, ValueError, EOFError):
        log.error("Invalid selection.")
        return None


def _install_shutdown_signals() -> None:
    # Ctrl+Break from a shared console behaves like Ctrl+C.
    def _interrupt(signum, frame):
        raise KeyboardInterrupt

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)


def watch_stdin(stream, on_close) -> threading.Thread:
    """Call ``on_close`` once ``stream`` reaches EOF.

    A supervisor without a console (the tray runs under pythonw) can't send
    Ctrl+Break, so it holds our stdin open and closes it to stop us. If the
    supervisor dies, the pipe closes too, so the backend is never orphaned.
    """
    def run() -> None:
        try:
            while stream.read(1024):
                pass
        except (OSError, ValueError):
            pass
        on_close()

    thread = threading.Thread(target=run, name="stdin-watch", daemon=True)
    thread.start()
    return thread


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_file = args.log_file or (log_dir() / "netsleuth.log")
    configure_logging("DEBUG" if args.verbose else "INFO", log_file=log_file)

    settings = Settings.load()
    host = args.host or ("0.0.0.0" if settings.lan_exposure else "127.0.0.1")
    log.info("NetSleuth %s starting", __version__)

    # Deferred imports: scapy and friends are slow to load and not needed for --help.
    from .utils.network_utils import get_active_interfaces, interface_info

    iface = choose_interface(args.interface, get_active_interfaces(), args.headless)
    if iface is None:
        return EXIT_USAGE

    if port_in_use(host, args.port):
        log.error("Port %d is already in use on %s.", args.port, host)
        return EXIT_PORT_IN_USE

    info = interface_info(iface)
    if info is None:
        log.error("Interface %r has no IPv4 address.", iface)
        return EXIT_USAGE

    return run(args, settings, host, info)


def run(args, settings: Settings, host: str, info) -> int:
    from .core.capture import CaptureError, CapturePermissionError, run_capture
    from .core.discovery import Discovery
    from .core.events import EventEngine
    from .core.legacy import import_legacy
    from .core.pipeline import Pipeline
    from .core.store import DeviceStore
    from .settings import db_path
    from .utils.network_utils import default_gateway_ip
    from .web.api import AppContext, Server, create_app, default_static_dir

    gateway = default_gateway_ip()
    if gateway and ip_address(gateway) not in info.network:
        gateway = None
    log.info("Monitoring %s (%s on %s, gateway %s)", info.name, info.ip, info.network, gateway or "unknown")

    store = DeviceStore(db_path())
    import_legacy(store)
    store.start()
    engine = EventEngine(store, gateway, first_run=not store.list_events(limit=1))
    pipeline = Pipeline(
        store, info.network, gateway, engine,
        offline_timeout_s=lambda: settings.offline_timeout_s,
        retention_days=lambda: settings.retention_days,
    )
    discovery = Discovery(pipeline, info.name, info.ip, lambda: settings.sweep_interval_s)

    static_dir = default_static_dir()
    app = create_app(AppContext(
        store=store, engine=engine, settings=settings, pipeline=pipeline,
        interface=info.name, dev=args.dev, static_dir=static_dir,
    ))
    server = Server(app, host, args.port)

    _install_shutdown_signals()
    if args.exit_on_stdin_close and sys.stdin is not None:
        watch_stdin(sys.stdin.buffer, _thread.interrupt_main)
    pipeline.start()
    discovery.start()
    server.start()
    log.info("Dashboard at http://%s:%d", "localhost" if host == "127.0.0.1" else host, args.port)
    if not static_dir.is_dir():
        log.warning("UI not built (%s missing); only the API is served.", static_dir)
    if host != "127.0.0.1":
        log.warning("Dashboard is reachable from your LAN (bound to %s).", host)

    code = EXIT_OK
    try:
        run_capture(info.name, pipeline.submit)
    except KeyboardInterrupt:
        pass
    except CapturePermissionError as e:
        log.error("Packet capture permission denied: %s", e)
        log.error("Run from an administrator terminal, or reinstall Npcap without admin-only restriction.")
        code = EXIT_PERMISSION
    except CaptureError as e:
        log.error("Capture failed: %s", e)
        code = EXIT_ERROR
    except Exception:
        log.exception("Capture stopped unexpectedly.")
        code = EXIT_ERROR
    finally:
        log.info("Shutting down.")
        discovery.stop()
        pipeline.stop()
        server.close()
        store.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
