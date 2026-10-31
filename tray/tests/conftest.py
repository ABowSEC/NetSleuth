import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Keep tray files (config, PID file, logs) out of the real data directory."""
    monkeypatch.setenv("NETSLEUTH_HOME", str(tmp_path / "home"))
    return tmp_path / "home"
