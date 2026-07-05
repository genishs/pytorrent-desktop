"""Tests for :mod:`pytorrent_desktop.ui.main_window.MainWindow`.

Uses a fake engine (same call surface as
:class:`~pytorrent_desktop.core.engine.TorrentEngine`, no libtorrent/network
underneath) so these stay fast, deterministic widget tests rather than
integration tests against a real session.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

import pytorrent_desktop.ui.main_window as main_window_module
from pytorrent_desktop.core.config import AppSettings, OnCompleteSettings, SearchSettings
from pytorrent_desktop.core.engine import ProxyConfig, TorrentStatus
from pytorrent_desktop.core.errors import UnknownTorrentError
from pytorrent_desktop.core.search.base import SearchProvider
from pytorrent_desktop.ui.main_window import MainWindow
from pytorrent_desktop.ui.models import Column


class FakeEngine:
    """Minimal stand-in for TorrentEngine's call surface used by MainWindow."""

    def __init__(self, torrents: list[TorrentStatus] | None = None) -> None:
        self._torrents = list(torrents or [])
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.removed: list[tuple[str, bool]] = []
        self.moved: list[tuple[str, str]] = []
        self.sequential_queue_calls: list[bool] = []
        self.configure_privacy_calls: list[ProxyConfig | None] = []
        self.listen_port_calls: list[int] = []
        self.shutdown_calls = 0
        self.add_magnet_calls: list[tuple[str, str]] = []
        self.probe_dht_peers_calls: list[tuple[str, float]] = []
        self._privacy_status = "disabled"
        self._probe_dht_peers_result: int | None = None

    def snapshot(self) -> list[TorrentStatus]:
        return list(self._torrents)

    def add_magnet(self, magnet_uri: str, save_path: str) -> str:
        self.add_magnet_calls.append((magnet_uri, save_path))
        return "a" * 40

    def pause(self, info_hash: str) -> None:
        if info_hash not in {t.info_hash for t in self._torrents}:
            raise UnknownTorrentError(info_hash)
        self.paused.append(info_hash)
        self._torrents = [
            t.__class__(**{**t.__dict__, "is_paused": True}) if t.info_hash == info_hash else t
            for t in self._torrents
        ]

    def resume(self, info_hash: str) -> None:
        self.resumed.append(info_hash)
        self._torrents = [
            t.__class__(**{**t.__dict__, "is_paused": False}) if t.info_hash == info_hash else t
            for t in self._torrents
        ]

    def remove(self, info_hash: str, *, delete_data: bool = False) -> None:
        self.removed.append((info_hash, delete_data))
        self._torrents = [t for t in self._torrents if t.info_hash != info_hash]

    def move_in_queue(self, info_hash: str, direction: str) -> None:
        if info_hash not in {t.info_hash for t in self._torrents}:
            raise UnknownTorrentError(info_hash)
        self.moved.append((info_hash, direction))

    def set_sequential_queue(self, one_at_a_time: bool) -> None:
        self.sequential_queue_calls.append(one_at_a_time)

    def configure_privacy(self, cfg: ProxyConfig | None) -> None:
        self.configure_privacy_calls.append(cfg)
        self._privacy_status = "enabled" if cfg is not None else "disabled"

    def set_listen_port(self, port: int) -> None:
        self.listen_port_calls.append(port)

    def privacy_status(self) -> str:
        return self._privacy_status

    def shutdown(self, timeout_s: float = 10.0) -> None:
        self.shutdown_calls += 1

    def probe_dht_peers(self, info_hash: str, timeout: float = 10.0) -> int | None:
        self.probe_dht_peers_calls.append((info_hash, timeout))
        return self._probe_dht_peers_result

    def set_finished(self, info_hash: str, finished: bool) -> None:
        """Test helper: flip a torrent's ``is_finished`` in place."""
        self._torrents = [
            t.__class__(**{**t.__dict__, "is_finished": finished})
            if t.info_hash == info_hash
            else t
            for t in self._torrents
        ]


def make_status(**overrides) -> TorrentStatus:
    defaults = dict(
        info_hash="a" * 40,
        name="example.iso",
        save_path="D:\\Downloads",
        total_bytes=1000,
        downloaded_bytes=500,
        progress=0.5,
        download_rate=100,
        upload_rate=50,
        num_peers=3,
        num_seeds=1,
        state="downloading",
        is_paused=False,
        is_finished=False,
        queue_position=-1,
        error=None,
    )
    defaults.update(overrides)
    return TorrentStatus(**defaults)


def test_main_window_with_empty_engine_has_zero_rows(qtbot):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    assert window._model.rowCount() == 0


def test_main_window_populates_model_from_snapshot(qtbot):
    engine = FakeEngine([make_status(info_hash="a" * 40), make_status(info_hash="b" * 40)])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    assert window._model.rowCount() == 2


def test_pause_action_disabled_with_no_selection(qtbot):
    engine = FakeEngine([make_status()])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    assert not window._pause_action.isEnabled()
    assert not window._resume_action.isEnabled()
    assert not window._remove_action.isEnabled()


def test_pause_action_enabled_when_running_torrent_selected(qtbot):
    engine = FakeEngine([make_status(is_paused=False)])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window._table_view.selectRow(0)
    assert window._pause_action.isEnabled()
    assert not window._resume_action.isEnabled()
    assert window._remove_action.isEnabled()


def test_resume_action_enabled_when_paused_torrent_selected(qtbot):
    engine = FakeEngine([make_status(is_paused=True)])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window._table_view.selectRow(0)
    assert not window._pause_action.isEnabled()
    assert window._resume_action.isEnabled()


def test_pause_selected_calls_engine_pause(qtbot):
    engine = FakeEngine([make_status(info_hash="a" * 40, is_paused=False)])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window._table_view.selectRow(0)
    window._pause_selected()
    assert engine.paused == ["a" * 40]


def test_status_bar_reports_aggregate_rates_and_active_count(qtbot):
    engine = FakeEngine(
        [
            make_status(
                info_hash="a" * 40, download_rate=1000, upload_rate=200, state="downloading"
            ),
            make_status(info_hash="b" * 40, download_rate=0, upload_rate=0, is_paused=True),
        ]
    )
    window = MainWindow(engine)
    qtbot.addWidget(window)
    message = window._status_bar.currentMessage()
    assert "활성 1/2" in message


def test_column_enum_matches_seven_ux_spec_columns():
    assert len(Column) == 7


def test_move_selected_up_calls_engine_move_in_queue(qtbot):
    engine = FakeEngine([make_status(info_hash="a" * 40)])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window._table_view.selectRow(0)

    window._move_selected("up")

    assert engine.moved == [("a" * 40, "up")]


def test_move_selected_down_calls_engine_move_in_queue(qtbot):
    engine = FakeEngine([make_status(info_hash="a" * 40)])
    window = MainWindow(engine)
    qtbot.addWidget(window)
    window._table_view.selectRow(0)

    window._move_selected("down")

    assert engine.moved == [("a" * 40, "down")]


def test_sequential_queue_toolbar_toggle_defaults_checked(qtbot):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    assert window._sequential_queue_action.isChecked()


def test_toggling_sequential_queue_action_calls_engine(qtbot):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)

    window._sequential_queue_action.setChecked(False)

    assert engine.sequential_queue_calls[-1] is False


# -- status bar proxy indicator (docs/UX-SPEC.md §1.4) ------------------------


def test_status_bar_shows_proxy_not_configured_by_default(qtbot):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    assert "프록시: 미설정" in window._status_bar.currentMessage()


def test_status_bar_shows_proxy_applied_once_configured(qtbot):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)

    engine.configure_privacy(ProxyConfig(host="127.0.0.1", port=1080))
    window._poll()

    assert "프록시: ● 적용됨" in window._status_bar.currentMessage()


# -- settings dialog integration (docs/UX-SPEC.md §4) -------------------------


class _FakeSettingsDialog:
    """Test double standing in for the real ``SettingsDialog``.

    Bypasses actually constructing/showing Qt widgets — MainWindow only ever
    calls ``exec()`` and the accessor methods after Accepted, so this only
    needs to mimic that surface.
    """

    DialogCode = QDialog.DialogCode

    def __init__(self, settings, *, initial_password=None, parent=None) -> None:
        self.settings = settings
        self.initial_password = initial_password

    def exec(self):
        return QDialog.DialogCode.Accepted

    def proxy_enabled(self) -> bool:
        return True

    def proxy_host(self) -> str:
        return "127.0.0.1"

    def proxy_port(self) -> int:
        return 1080

    def proxy_username(self) -> str | None:
        return None

    def proxy_password(self) -> str | None:
        return "secret"

    def kill_switch(self) -> bool:
        return True

    def listen_port(self) -> int:
        return 7000

    def default_save_path(self) -> str:
        return "D:\\NewDownloads"

    def on_complete_action(self) -> str:
        return "none"

    def search_enabled(self) -> bool:
        return False

    def search_btdig_base_url(self) -> str:
        return "https://btdig.com"

    def search_consent_accepted(self) -> bool:
        return False


def test_settings_dialog_accept_applies_proxy_and_listen_port(qtbot, monkeypatch):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    monkeypatch.setattr(main_window_module, "SettingsDialog", _FakeSettingsDialog)

    window._open_settings_dialog()

    assert engine.listen_port_calls == [7000]
    assert len(engine.configure_privacy_calls) == 1
    cfg = engine.configure_privacy_calls[0]
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 1080
    assert cfg.password == "secret"
    assert window._settings.proxy.enabled is True
    assert window._settings.listen_port == 7000
    assert window._settings.default_save_path == "D:\\NewDownloads"
    assert window._proxy_password == "secret"  # kept in memory only (D2)


def test_settings_dialog_cancel_does_not_touch_engine(qtbot, monkeypatch):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)

    class _RejectingSettingsDialog(_FakeSettingsDialog):
        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window_module, "SettingsDialog", _RejectingSettingsDialog)

    window._open_settings_dialog()

    assert engine.configure_privacy_calls == []
    assert engine.listen_port_calls == []


def test_settings_dialog_persists_via_config_store(qtbot, monkeypatch, tmp_path):
    from pytorrent_desktop.core.config import AppPaths, ConfigStore

    store = ConfigStore(AppPaths(tmp_path))
    engine = FakeEngine()
    window = MainWindow(engine, config_store=store)
    qtbot.addWidget(window)
    monkeypatch.setattr(main_window_module, "SettingsDialog", _FakeSettingsDialog)

    window._open_settings_dialog()

    reloaded = store.load()
    assert reloaded.listen_port == 7000
    assert reloaded.proxy.enabled is True
    assert reloaded.proxy.host == "127.0.0.1"
    # D2: the password must never round-trip through the on-disk config.
    assert not hasattr(reloaded.proxy, "password")


# -- on-complete countdown (docs/DECISIONS.md D3, docs/ARCHITECTURE.md §4.4) ----


def _make_fake_countdown_dialog(calls: list, result):
    """Test double for OnCompleteCountdownDialog: records construction args
    and returns a preset result immediately, with no real timer/UI — so
    these tests run instantly instead of waiting out a real 30s countdown."""

    class _FakeCountdownDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, seconds, still_eligible, *, action_description="", parent=None):
            calls.append((seconds, action_description))
            self._still_eligible = still_eligible

        def exec(self):
            return result

    return _FakeCountdownDialog


def test_on_complete_none_never_starts_a_countdown(qtbot, monkeypatch):
    status = make_status(info_hash="a" * 40, is_finished=False)
    engine = FakeEngine([status])
    calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog(calls, QDialog.DialogCode.Accepted),
    )
    window = MainWindow(engine)  # default settings: on_complete.action == "none"
    qtbot.addWidget(window)

    engine.set_finished("a" * 40, True)
    window._poll()

    assert calls == []


def test_on_complete_not_triggered_for_already_finished_restored_torrent(qtbot, monkeypatch):
    """A torrent that's already finished/seeding when the window is built
    (e.g. restored from resume data) must not immediately arm the countdown
    — only a real not-finished -> finished transition observed this session
    counts (docs/ARCHITECTURE.md §4.4)."""
    status = make_status(info_hash="a" * 40, is_finished=True, state="seeding")
    engine = FakeEngine([status])
    calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog(calls, QDialog.DialogCode.Accepted),
    )
    settings = AppSettings(on_complete=OnCompleteSettings(action="quit_app"))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    window._poll()

    assert calls == []


def test_on_complete_triggers_after_a_real_completion_transition(qtbot, monkeypatch):
    status = make_status(info_hash="a" * 40, is_finished=False, state="downloading")
    engine = FakeEngine([status])
    calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog(calls, QDialog.DialogCode.Accepted),
    )
    settings = AppSettings(on_complete=OnCompleteSettings(action="quit_app"))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)
    assert calls == []  # not finished yet

    engine.set_finished("a" * 40, True)
    window._poll()

    assert len(calls) == 1
    assert engine.shutdown_calls == 1  # resume data flushed before quitting


def test_on_complete_quit_app_never_calls_the_system_shutdown_seam(qtbot, monkeypatch):
    status = make_status(info_hash="a" * 40, is_finished=False)
    engine = FakeEngine([status])
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog([], QDialog.DialogCode.Accepted),
    )
    shutdown_calls: list = []
    settings = AppSettings(on_complete=OnCompleteSettings(action="quit_app"))
    window = MainWindow(
        engine, settings=settings, system_shutdown_fn=lambda: shutdown_calls.append(1)
    )
    qtbot.addWidget(window)

    engine.set_finished("a" * 40, True)
    window._poll()

    assert shutdown_calls == []  # "quit_app" must never invoke the OS shutdown seam
    assert engine.shutdown_calls == 1


def test_on_complete_shutdown_system_calls_only_the_injected_seam(qtbot, monkeypatch):
    """Safety-critical: the real OS shutdown must only ever be reachable
    through the injected seam, never invoked directly by MainWindow, and
    this test (like all others) never lets a real shutdown happen."""
    status = make_status(info_hash="a" * 40, is_finished=False)
    engine = FakeEngine([status])
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog([], QDialog.DialogCode.Accepted),
    )
    shutdown_calls: list = []
    settings = AppSettings(on_complete=OnCompleteSettings(action="shutdown_system"))
    window = MainWindow(
        engine, settings=settings, system_shutdown_fn=lambda: shutdown_calls.append(1)
    )
    qtbot.addWidget(window)

    engine.set_finished("a" * 40, True)
    window._poll()

    assert shutdown_calls == [1]
    assert engine.shutdown_calls == 1


def test_on_complete_cancelled_does_not_retrigger_without_a_new_completion(qtbot, monkeypatch):
    status = make_status(info_hash="a" * 40, is_finished=False)
    engine = FakeEngine([status])
    calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog(calls, QDialog.DialogCode.Rejected),
    )
    settings = AppSettings(on_complete=OnCompleteSettings(action="quit_app"))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    engine.set_finished("a" * 40, True)
    window._poll()
    assert len(calls) == 1

    window._poll()  # still all-finished, but the countdown was cancelled

    assert len(calls) == 1  # must not retrigger without a fresh completion
    assert engine.shutdown_calls == 0  # cancelled -> the action never ran


def test_on_complete_countdown_uses_the_configured_duration(qtbot, monkeypatch):
    status = make_status(info_hash="a" * 40, is_finished=False)
    engine = FakeEngine([status])
    calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "OnCompleteCountdownDialog",
        _make_fake_countdown_dialog(calls, QDialog.DialogCode.Rejected),
    )
    settings = AppSettings(on_complete=OnCompleteSettings(action="shutdown_system"))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    engine.set_finished("a" * 40, True)
    window._poll()

    assert calls == [(30, "시스템을 종료")]  # docs/DECISIONS.md D3: 30s, never skipped


# -- search (v0.5.1a, EXPERIMENTAL/ALPHA — docs/ARCHITECTURE.md §9) -----------
#
# Fake stand-ins for SearchConsentDialog/SearchDialog, same test-double
# pattern as _FakeSettingsDialog/_make_fake_countdown_dialog above: no real
# Qt dialog is shown, only exec()'s return value and the small accessor
# surface MainWindow actually calls.


class _FakeProvider(SearchProvider):
    name = "fake-provider"

    def search(self, query: str, *, page: int = 0, timeout: float = 10.0) -> list:
        return []


def _make_fake_consent_dialog(calls: list, result):
    class _FakeSearchConsentDialog:
        DialogCode = QDialog.DialogCode

        def __init__(self, parent=None) -> None:
            calls.append("shown")

        def exec(self):
            return result

    return _FakeSearchConsentDialog


def _make_fake_search_dialog(result, *, magnet=None, save_path=None):
    class _FakeSearchDialog:
        DialogCode = QDialog.DialogCode
        constructed_with: list = []

        def __init__(
            self,
            provider,
            *,
            timeout=10.0,
            default_save_path="",
            probe_dht_peers_fn=None,
            parent=None,
        ) -> None:
            type(self).constructed_with.append(
                (provider, timeout, default_save_path, probe_dht_peers_fn)
            )

        def exec(self):
            return result

        def selected_magnet(self):
            return magnet

        def selected_save_path(self):
            return save_path

    return _FakeSearchDialog


def test_search_action_disabled_by_default(qtbot):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)
    assert not window._search_action.isEnabled()


def test_search_action_enabled_when_settings_search_enabled(qtbot):
    engine = FakeEngine()
    settings = AppSettings(search=SearchSettings(enabled=True, consent_accepted=True))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)
    assert window._search_action.isEnabled()


def test_open_search_dialog_is_a_noop_when_search_disabled(qtbot, monkeypatch):
    engine = FakeEngine()
    window = MainWindow(engine)
    qtbot.addWidget(window)

    fake_dialog = _make_fake_search_dialog(QDialog.DialogCode.Accepted)
    monkeypatch.setattr(main_window_module, "SearchDialog", fake_dialog)

    window._open_search_dialog()

    assert fake_dialog.constructed_with == []  # never even constructed
    assert engine.add_magnet_calls == []


def test_open_search_dialog_blocks_without_consent_when_declined(qtbot, monkeypatch):
    engine = FakeEngine()
    settings = AppSettings(search=SearchSettings(enabled=True, consent_accepted=False))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    consent_calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "SearchConsentDialog",
        _make_fake_consent_dialog(consent_calls, QDialog.DialogCode.Rejected),
    )
    fake_search_dialog = _make_fake_search_dialog(QDialog.DialogCode.Accepted)
    monkeypatch.setattr(main_window_module, "SearchDialog", fake_search_dialog)

    window._open_search_dialog()

    assert consent_calls == ["shown"]  # the gate was shown
    assert fake_search_dialog.constructed_with == []  # but search never ran
    assert engine.add_magnet_calls == []
    assert window._settings.search.consent_accepted is False  # declining doesn't persist


def test_open_search_dialog_proceeds_after_consent_accepted(qtbot, monkeypatch, tmp_path):
    from pytorrent_desktop.core.config import AppPaths, ConfigStore

    store = ConfigStore(AppPaths(tmp_path))
    engine = FakeEngine()
    settings = AppSettings(search=SearchSettings(enabled=True, consent_accepted=False))
    window = MainWindow(engine, config_store=store, settings=settings)
    qtbot.addWidget(window)

    consent_calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "SearchConsentDialog",
        _make_fake_consent_dialog(consent_calls, QDialog.DialogCode.Accepted),
    )
    magnet = "magnet:?xt=urn:btih:" + "d" * 40
    fake_search_dialog = _make_fake_search_dialog(
        QDialog.DialogCode.Accepted, magnet=magnet, save_path="D:\\SearchDownloads"
    )
    monkeypatch.setattr(main_window_module, "SearchDialog", fake_search_dialog)

    window._open_search_dialog()

    assert consent_calls == ["shown"]
    assert len(fake_search_dialog.constructed_with) == 1
    assert engine.add_magnet_calls == [(magnet, "D:\\SearchDownloads")]
    # Consent persists both in memory and on disk, so it isn't asked again.
    assert window._settings.search.consent_accepted is True
    assert store.load().search.consent_accepted is True


def test_open_search_dialog_forwards_the_probe_dht_peers_seam(qtbot, monkeypatch):
    """MainWindow must hand SearchDialog a callable wrapping
    TorrentEngine.probe_dht_peers (docs/DECISIONS.md D3's injected-seam
    pattern) — never let SearchDialog/SearchResultDetailDialog import or call
    TorrentEngine directly."""
    engine = FakeEngine()
    settings = AppSettings(search=SearchSettings(enabled=True, consent_accepted=True))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    fake_search_dialog = _make_fake_search_dialog(QDialog.DialogCode.Rejected)
    monkeypatch.setattr(main_window_module, "SearchDialog", fake_search_dialog)

    window._open_search_dialog()

    assert len(fake_search_dialog.constructed_with) == 1
    probe_fn = fake_search_dialog.constructed_with[0][3]
    assert probe_fn == engine.probe_dht_peers
    assert probe_fn("a" * 40, 5.0) is None
    assert engine.probe_dht_peers_calls == [("a" * 40, 5.0)]


def test_open_search_dialog_skips_consent_gate_once_already_accepted(qtbot, monkeypatch):
    engine = FakeEngine()
    settings = AppSettings(search=SearchSettings(enabled=True, consent_accepted=True))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    consent_calls: list = []
    monkeypatch.setattr(
        main_window_module,
        "SearchConsentDialog",
        _make_fake_consent_dialog(consent_calls, QDialog.DialogCode.Accepted),
    )
    magnet = "magnet:?xt=urn:btih:" + "e" * 40
    fake_search_dialog = _make_fake_search_dialog(
        QDialog.DialogCode.Accepted, magnet=magnet, save_path="D:\\SearchDownloads"
    )
    monkeypatch.setattr(main_window_module, "SearchDialog", fake_search_dialog)

    window._open_search_dialog()

    assert consent_calls == []  # never shown again once already accepted
    assert engine.add_magnet_calls == [(magnet, "D:\\SearchDownloads")]


def test_open_search_dialog_cancel_adds_nothing(qtbot, monkeypatch):
    engine = FakeEngine()
    settings = AppSettings(search=SearchSettings(enabled=True, consent_accepted=True))
    window = MainWindow(engine, settings=settings)
    qtbot.addWidget(window)

    fake_search_dialog = _make_fake_search_dialog(QDialog.DialogCode.Rejected)
    monkeypatch.setattr(main_window_module, "SearchDialog", fake_search_dialog)

    window._open_search_dialog()

    assert engine.add_magnet_calls == []
