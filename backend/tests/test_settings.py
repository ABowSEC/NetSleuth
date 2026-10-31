import pytest

from netsleuth.settings import Settings, config_path, data_dir


def test_data_dir_honours_netsleuth_home(isolated_home):
    assert data_dir() == isolated_home


def test_defaults_when_no_config():
    s = Settings.load()
    assert s.offline_timeout_s == 600
    assert s.lan_exposure is False


def test_save_and_reload_round_trip():
    s = Settings()
    s.update({"sweep_interval_s": 120, "lan_exposure": True})
    s.save()
    assert Settings.load() == s


def test_env_override(monkeypatch):
    monkeypatch.setenv("NETSLEUTH_RETENTION_DAYS", "7")
    monkeypatch.setenv("NETSLEUTH_ANOMALY_PLUGIN", "true")
    s = Settings.load()
    assert s.retention_days == 7
    assert s.anomaly_plugin is True


def test_invalid_config_file_falls_back_to_defaults():
    config_path().write_text("this is = = not toml", encoding="utf-8")
    assert Settings.load() == Settings()


@pytest.mark.parametrize(
    "changes",
    [
        {"nope": 1},
        {"sweep_interval_s": 5},
        {"retention_days": "30"},
        {"lan_exposure": 1},
        {"offline_timeout_s": True},
    ],
)
def test_update_rejects_bad_values(changes):
    s = Settings()
    with pytest.raises(ValueError):
        s.update(changes)
    assert s == Settings()


def test_update_is_all_or_nothing():
    s = Settings()
    with pytest.raises(ValueError):
        s.update({"retention_days": 10, "sweep_interval_s": 1})
    assert s.retention_days == 30
