import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Point NETSLEUTH_HOME at a temp dir so tests never touch real user data."""
    monkeypatch.setenv("NETSLEUTH_HOME", str(tmp_path))
    for key in ("OFFLINE_TIMEOUT_S", "SWEEP_INTERVAL_S", "RETENTION_DAYS", "LAN_EXPOSURE", "ANOMALY_PLUGIN"):
        monkeypatch.delenv(f"NETSLEUTH_{key}", raising=False)
    return tmp_path
