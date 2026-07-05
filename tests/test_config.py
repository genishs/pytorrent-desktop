"""Tests for :mod:`pytorrent_desktop.core.config`'s persisted settings (v0.4.0, §7).

Headless, filesystem-only — no libtorrent/Qt involved. Every test uses an
isolated ``tmp_path``-rooted :class:`AppPaths` rather than the real
``%APPDATA%`` location.
"""

from __future__ import annotations

import json
from pathlib import Path

from pytorrent_desktop.core.config import (
    AppPaths,
    AppSettings,
    ConfigStore,
    OnCompleteSettings,
    ProxySettings,
    SearchSettings,
    default_download_dir,
)


def test_default_settings_have_no_proxy_and_on_complete_none() -> None:
    settings = AppSettings()
    assert settings.proxy.enabled is False
    assert settings.on_complete.action == "none"
    assert settings.sequential_queue is True
    assert settings.listen_port == 6881


# -- search settings (v0.5.1a, EXPERIMENTAL/ALPHA) ----------------------------


def test_default_search_settings_are_disabled_with_no_consent() -> None:
    settings = AppSettings()
    assert settings.search.enabled is False
    assert settings.search.consent_accepted is False
    assert settings.search.btdig_base_url == "https://btdig.com"
    assert settings.search.timeout == 10.0


def test_proxy_settings_has_no_password_field() -> None:
    # D2: the persisted subset must not even have a place to put a password.
    assert not hasattr(ProxySettings(), "password")


def test_load_with_no_config_file_returns_defaults(tmp_path: Path) -> None:
    store = ConfigStore(AppPaths(tmp_path))
    settings = store.load()
    assert settings == AppSettings()


def test_save_then_load_round_trips_all_fields(tmp_path: Path) -> None:
    store = ConfigStore(AppPaths(tmp_path))
    original = AppSettings(
        listen_port=12345,
        default_save_path=str(tmp_path / "downloads"),
        sequential_queue=False,
        proxy=ProxySettings(enabled=True, host="proxy.example", port=1080, username="alice",
                             kill_switch=False),
        on_complete=OnCompleteSettings(action="shutdown_system"),
        search=SearchSettings(
            enabled=True,
            btdig_base_url="https://btdig.example",
            timeout=15.0,
            consent_accepted=True,
        ),
    )

    store.save(original)
    loaded = store.load()

    assert loaded == original


def test_search_settings_round_trip_when_disabled_and_not_consented(tmp_path: Path) -> None:
    store = ConfigStore(AppPaths(tmp_path))
    original = AppSettings(search=SearchSettings())

    store.save(original)
    loaded = store.load()

    assert loaded.search.enabled is False
    assert loaded.search.consent_accepted is False


def test_load_falls_back_to_default_search_settings_when_missing(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    paths.config_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    store = ConfigStore(paths)
    settings = store.load()

    assert settings.search == SearchSettings()


def test_save_never_writes_a_password_field(tmp_path: Path) -> None:
    """D2: even if a caller somehow got a password onto the dataclass tree,
    ``ProxySettings`` has no such field, so the round trip can't leak one."""
    paths = AppPaths(tmp_path)
    store = ConfigStore(paths)
    settings = AppSettings(
        proxy=ProxySettings(enabled=True, host="proxy.example", port=1080, username="alice")
    )

    store.save(settings)

    raw = json.loads(paths.config_path.read_text(encoding="utf-8"))
    assert "password" not in raw["proxy"]
    assert set(raw["proxy"]) == {"enabled", "host", "port", "username", "kill_switch"}


def test_save_writes_atomically_via_tmp_file_replace(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    store = ConfigStore(paths)
    store.save(AppSettings())

    assert paths.config_path.is_file()
    assert not paths.config_path.with_suffix(".json.tmp").exists()


def test_load_falls_back_to_defaults_on_corrupt_json(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    paths.config_path.write_text("not valid json{{{", encoding="utf-8")

    store = ConfigStore(paths)
    settings = store.load()

    assert settings == AppSettings()


def test_load_falls_back_to_defaults_on_missing_expected_shape(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    paths.config_path.write_text(json.dumps({"unexpected": "shape"}), encoding="utf-8")

    store = ConfigStore(paths)
    settings = store.load()

    assert settings == AppSettings()


def test_load_rejects_unknown_on_complete_action(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    paths.config_path.write_text(
        json.dumps({"on_complete": {"action": "delete_everything"}}), encoding="utf-8"
    )

    store = ConfigStore(paths)
    settings = store.load()

    assert settings.on_complete.action == "none"


def test_default_download_dir_is_under_home_downloads() -> None:
    path = default_download_dir()
    assert path.parent.name == "Downloads"
    assert path.name == "pytorrent-desktop"
