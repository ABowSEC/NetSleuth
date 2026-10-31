"""Command-line entry point: ``python -m netsleuth``.

Exit codes follow docs/API_CONTRACT.md:
0 clean shutdown, 1 other error, 2 usage/config error,
3 capture permission denied, 4 port in use.
"""
from __future__ import annotations

import argparse
import logging
import signal
import socket
import sys
import threading

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
    # The tray supervisor stops us with CTRL_BREAK on Windows; treat it like Ctrl+C.
    def _interrupt(signum, frame):
        raise KeyboardInterrupt

    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _interrupt)
    signal.signal(signal.SIGTERM, _interrupt)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log_file = args.log_file or (log_dir() / "netsleuth.log")
    configure_logging("DEBUG" if args.verbose else "INFO", log_file=log_file)

    settings = Settings.load()
    host = args.host or ("0.0.0.0" if settings.lan_exposure else "127.0.0.1")
    log.info("NetSleuth %s starting", __version__)

    # Deferred imports: scapy and friends are slow to load and not needed for --help.
    from .utils.network_utils import get_active_interfaces

    iface = choose_interface(args.interface, get_active_interfaces(), args.headless)
    if iface is None:
        return EXIT_USAGE

    if port_in_use(host, args.port):
        log.error("Port %d is already in use on %s.", args.port, host)
        return EXIT_PORT_IN_USE

    from .core.sniffer import start_sniffing
    from .web.web_interface import start_web_interface

    _install_shutdown_signals()

    threading.Thread(
        target=start_web_interface, kwargs={"host": host, "port": args.port}, daemon=True, name="web"
    ).start()
    log.info("Dashboard at http://%s:%d", "localhost" if host == "127.0.0.1" else host, args.port)
    if host != "127.0.0.1":
        log.warning("Dashboard is reachable from your LAN (bound to %s).", host)

    try:
        start_sniffing(interface=iface, packet_count=0)
    except KeyboardInterrupt:
        log.info("Shutting down.")
        return EXIT_OK
    except PermissionError as e:
        log.error("Packet capture permission denied: %s", e)
        log.error("Run from an administrator terminal, or reinstall Npcap without admin-only restriction.")
        return EXIT_PERMISSION
    except Exception:
        log.exception("Capture stopped unexpectedly.")
        return EXIT_ERROR
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
