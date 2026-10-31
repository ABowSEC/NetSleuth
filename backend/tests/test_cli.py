import socket

import pytest

from netsleuth import cli


def test_explicit_interface_must_exist():
    assert cli.choose_interface("eth9", ["Wi-Fi", "Ethernet"], headless=True) is None
    assert cli.choose_interface("Wi-Fi", ["Wi-Fi", "Ethernet"], headless=True) == "Wi-Fi"


def test_single_interface_is_auto_selected():
    assert cli.choose_interface(None, ["Wi-Fi"], headless=True) == "Wi-Fi"


def test_headless_refuses_to_prompt(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: pytest.fail("prompted in headless mode"))
    assert cli.choose_interface(None, ["Wi-Fi", "Ethernet"], headless=True) is None


def test_interactive_prompt(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "2")
    assert cli.choose_interface(None, ["Wi-Fi", "Ethernet"], headless=False) == "Ethernet"


def test_port_in_use_detects_listener():
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        assert cli.port_in_use("127.0.0.1", port)
    assert not cli.port_in_use("127.0.0.1", port)


def test_headless_without_interface_exits_usage(monkeypatch):
    monkeypatch.setattr("netsleuth.utils.network_utils.get_active_interfaces", lambda: ["Wi-Fi", "Ethernet"])
    assert cli.main(["--headless"]) == cli.EXIT_USAGE


def test_port_conflict_exits_4(monkeypatch):
    monkeypatch.setattr("netsleuth.utils.network_utils.get_active_interfaces", lambda: ["Wi-Fi"])
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        port = server.getsockname()[1]
        assert cli.main(["--headless", "--port", str(port)]) == cli.EXIT_PORT_IN_USE


def test_watch_stdin_fires_on_eof():
    import os
    import threading

    read_fd, write_fd = os.pipe()
    closed = threading.Event()
    with os.fdopen(read_fd, "rb") as reader:
        thread = cli.watch_stdin(reader, closed.set)
        os.write(write_fd, b"still here")
        assert not closed.wait(0.2)
        os.close(write_fd)
        assert closed.wait(2)
        thread.join(2)


def test_exit_on_stdin_close_flag_parses():
    assert cli.build_parser().parse_args(["--exit-on-stdin-close"]).exit_on_stdin_close
