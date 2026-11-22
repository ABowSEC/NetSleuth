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
import time
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
EXIT_NETWORK_CHANGED = 5     # moved to another network: the supervisor restarts us straight away


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

    replay = parser.add_argument_group("replay (offline testing: reads a capture file, sends nothing)")
    replay.add_argument("--replay", metavar="FILE", help="replay a .pcap file in place of live capture")
    replay.add_argument("--replay-speed", type=float, default=0.0, metavar="N",
                        help="0 = as fast as possible (default), 1 = original pacing, 10 = ten times faster")
    replay.add_argument("--replay-exit", action="store_true",
                        help="exit when the file is finished (default: keep serving the dashboard)")
    replay.add_argument("--subnet", metavar="CIDR", help="the LAN in the capture (default: inferred)")
    replay.add_argument("--gateway", metavar="IP", help="the router's IP in the capture (default: none)")
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
    # Headless runs are supervised: the log file is the record, and stderr is kept
    # for crashes only (the tray saves it to backend-stderr.log).
    configure_logging("DEBUG" if args.verbose else "INFO", log_file=log_file, console=not args.headless)

    settings = Settings.load()
    host = args.host or ("0.0.0.0" if settings.lan_exposure else "127.0.0.1")
    log.info("NetSleuth %s starting", __version__)

    if args.replay:
        if port_in_use(host, args.port):
            log.error("Port %d is already in use on %s.", args.port, host)
            return EXIT_PORT_IN_USE
        return run_replay(args, settings, host)

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


def identify_network(info, attempts: int = 5, delay_s: float = 2.0):
    """Fingerprint the network ``info`` is on. Sends nothing.

    The router's MAC is read from the OS ARP cache. Right after connecting it
    may not be there yet, so wait briefly for the OS to resolve it on its own.
    """
    from .core.networks import Fingerprint, current_fingerprint

    fp = None
    for attempt in range(attempts):
        fp = current_fingerprint(info.name)
        if fp is None or fp.gateway_mac or not fp.gateway_ip:
            break
        if attempt < attempts - 1:
            time.sleep(delay_s)
    if fp is None:
        fp = Fingerprint(str(info.network), info.ip)
    if fp.gateway_ip and not fp.gateway_mac:
        log.warning("Router %s isn't in the ARP cache; identifying this network by subnet and name only.",
                    fp.gateway_ip)
    return fp


def run(args, settings: Settings, host: str, info) -> int:
    from .core.capture import CaptureError, CapturePermissionError, run_capture
    from .core.discovery import Discovery
    from .core.events import EventEngine
    from .core.identify_mode import IdentifySession
    from .core.legacy import import_legacy
    from .core.networks import NetworkRegistry, NetworkWatch, apply_pending_reset
    from .core.pipeline import Pipeline
    from .core.store import DeviceStore
    from .settings import data_dir, db_path
    from .web.api import AppContext, Server, create_app, default_static_dir

    fp = identify_network(info)
    gateway = fp.gateway_ip
    was_reset = apply_pending_reset(data_dir())
    registry = NetworkRegistry(data_dir())
    if was_reset:
        registry.set_meta("reset_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    network, created = registry.resolve(fp)
    # The old device list moves only when the user chose it on the dashboard (never guessed).
    pending = registry.take_pending_adoption(network.id)
    if pending and registry.adopt_legacy(network.id, db_path(), trust=pending):
        network = registry.get(network.id)
    log.info("Network %s (%s, %s on %s, router %s): %s",
             network.id, network.display_name, info.ip, info.network, gateway or "unknown", network.trust)

    # Live view of this network's trust and link, read on every packet.
    state = {"trust": network.trust, "link": True}

    def capturing_allowed() -> bool:
        return state["trust"] != "idle" and state["link"]

    store = DeviceStore(registry.db_path(network.id))
    if network.trust == "home" and not registry.get_meta("reset_at"):
        import_legacy(store)          # pre-refactor names belong to the home inventory only; not after a reset
    store.start()
    engine = EventEngine(store, gateway, first_run=not store.list_events(limit=1), own_mac=info.mac)
    pipeline = Pipeline(
        store, info.network, gateway, engine,
        offline_timeout_s=lambda: settings.offline_timeout_s,
        retention_days=lambda: settings.retention_days,
        accept=capturing_allowed,
    )
    discovery = Discovery(pipeline, info.name, info.ip, lambda: settings.sweep_interval_s,
                          enabled=lambda: state["trust"] == "home" and state["link"])
    identify = IdentifySession(
        store, engine, info.network, info.ip, own_mac=info.mac, gateway_ip=gateway,
        port_check_enabled=lambda: settings.port_check, is_paused=lambda: pipeline.paused,
    )

    def on_network_update(changed_network) -> None:
        if changed_network.id != network.id:
            return
        if changed_network.trust != state["trust"]:
            log.info("This network is now %s", changed_network.trust)
        state["trust"] = changed_network.trust
        if changed_network.trust != "home" and identify.status()["running"]:
            identify.stop(wait=0)

    registry.subscribe(on_network_update)

    if created and network.similar_to:
        twin = registry.get(network.similar_to)
        if twin and twin.trust == "home":
            engine.emit(
                "alert", "high",
                f"This network is called {network.ssid!r}, like your network {twin.display_name}, "
                "but its router is different. If you replaced your router, set this network to Home. "
                "If not, another device may be imitating your network. NetSleuth stays idle here.",
                rule="network_lookalike", similar_to=twin.id, network=network.id,
            )

    network_changed = threading.Event()

    def on_change(_new_fp) -> None:
        network_changed.set()
        _thread.interrupt_main()

    def on_link(up: bool) -> None:
        if up != state["link"]:
            log.info("Network link %s", "back" if up else "lost; pausing until it returns")
        state["link"] = up

    watch = NetworkWatch(info.name, fp, on_change=on_change, on_link=on_link)

    def request_restart() -> None:
        """Restart soon (after the API has answered), e.g. to adopt the old device list."""
        def later() -> None:
            time.sleep(0.5)
            on_change(None)
        threading.Thread(target=later, name="restart", daemon=True).start()

    static_dir = default_static_dir()
    app = create_app(AppContext(
        store=store, engine=engine, settings=settings, pipeline=pipeline,
        interface=info.name, dev=args.dev, static_dir=static_dir, identify=identify,
        networks=registry, network_id=network.id, legacy_db=db_path(), request_restart=request_restart,
        data_root=data_dir(),
    ))
    server = Server(app, host, args.port)

    _install_shutdown_signals()
    if args.exit_on_stdin_close and sys.stdin is not None:
        watch_stdin(sys.stdin.buffer, _thread.interrupt_main)
    pipeline.start()
    discovery.start()
    watch.start()
    server.start()
    log.info("Dashboard at http://%s:%d", "localhost" if host == "127.0.0.1" else host, args.port)
    if not static_dir.is_dir():
        log.warning("UI not built (%s missing); only the API is served.", static_dir)
    if host != "127.0.0.1":
        log.warning("Dashboard is reachable from your LAN (bound to %s).", host)
    if network.trust == "idle":
        log.info("NetSleuth is idle on this network: nothing is captured. "
                 "Set it to Home or Observe on the dashboard to start.")

    code = EXIT_OK
    idle = threading.Event()        # never set; waited on for responsive idling
    try:
        while True:
            if state["trust"] == "idle":
                idle.wait(1)
                continue
            engine.begin()
            run_capture(info.name, pipeline.submit, stop=lambda: state["trust"] == "idle")
            if state["trust"] != "idle":
                # Capture ended without being asked to idle: treat it as a stop request.
                raise KeyboardInterrupt
            log.info("Capture stopped: this network was set to idle.")
    except KeyboardInterrupt:
        if network_changed.is_set():
            log.info("Restarting to switch network profiles.")
            code = EXIT_NETWORK_CHANGED
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
        watch.stop()
        identify.stop(wait=5)
        discovery.stop()
        pipeline.stop()
        server.close()
        store.close()
    return code


def replay_db_path():
    """A throwaway database for replays, so they never touch the real inventory."""
    from .settings import data_dir

    folder = data_dir() / "replay"
    folder.mkdir(exist_ok=True)
    return folder / "devices.db"


def run_replay(args, settings: Settings, host: str) -> int:
    """Run the pipeline, events and API on a capture file. Sends no packets."""
    from ipaddress import ip_network
    from pathlib import Path

    from .core.events import EventEngine
    from .core.pipeline import Pipeline
    from .core.replay import ReplayClock, ReplayError, first_timestamp, infer_network, replay
    from .core.store import DeviceStore
    from .web.api import AppContext, Server, create_app, default_static_dir

    path = Path(args.replay)
    try:
        network = ip_network(args.subnet, strict=False) if args.subnet else infer_network(path)
        start = first_timestamp(path)
    except ValueError as e:
        log.error("Bad --subnet: %s", e)
        return EXIT_USAGE
    except ReplayError as e:
        log.error("%s", e)
        return EXIT_USAGE
    if network is None:
        log.error("Couldn't tell which subnet %s is from; pass --subnet.", path)
        return EXIT_USAGE
    if args.gateway and ip_address(args.gateway) not in network:
        log.error("Gateway %s isn't in %s.", args.gateway, network)
        return EXIT_USAGE

    db = replay_db_path()
    for leftover in (db, db.with_name(db.name + "-wal"), db.with_name(db.name + "-shm")):
        leftover.unlink(missing_ok=True)
    log.info("Replaying %s (subnet %s, gateway %s) into %s", path, network, args.gateway or "unknown", db)

    clock = ReplayClock(start or 0.0)
    store = DeviceStore(db)
    store.start()
    engine = EventEngine(store, args.gateway, clock=clock, first_run=True)
    pipeline = Pipeline(
        store, network, args.gateway, engine,
        offline_timeout_s=lambda: settings.offline_timeout_s,
        retention_days=lambda: settings.retention_days,
    )
    app = create_app(AppContext(
        store=store, engine=engine, settings=settings, pipeline=pipeline,
        interface=f"replay:{path.name}", dev=args.dev, static_dir=default_static_dir(), identify=None,
    ))
    server = Server(app, host, args.port)

    _install_shutdown_signals()
    if args.exit_on_stdin_close and sys.stdin is not None:
        watch_stdin(sys.stdin.buffer, _thread.interrupt_main)
    pipeline.start()
    server.start()
    log.info("Dashboard at http://%s:%d", "localhost" if host == "127.0.0.1" else host, args.port)

    code = EXIT_OK
    stop = threading.Event()
    try:
        replay(path, pipeline, clock=clock, speed=args.replay_speed, stop=stop)
        store.flush()
        if not args.replay_exit:
            log.info("Replay finished; still serving the dashboard. Press Ctrl+C to stop.")
            while True:
                stop.wait(1)       # short waits keep Ctrl+C responsive on Windows
    except KeyboardInterrupt:
        stop.set()
    except ReplayError as e:
        log.error("%s", e)
        code = EXIT_USAGE
    except Exception:
        log.exception("Replay stopped unexpectedly.")
        code = EXIT_ERROR
    finally:
        log.info("Shutting down.")
        pipeline.stop()
        server.close()
        store.close()
    return code


if __name__ == "__main__":
    sys.exit(main())
