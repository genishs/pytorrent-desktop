"""Tests for :mod:`pytorrent_desktop.ui.main_window.MainWindow`.

Uses a fake engine (same call surface as
:class:`~pytorrent_desktop.core.engine.TorrentEngine`, no libtorrent/network
underneath) so these stay fast, deterministic widget tests rather than
integration tests against a real session.
"""

from __future__ import annotations

from pytorrent_desktop.core.engine import TorrentStatus
from pytorrent_desktop.core.errors import UnknownTorrentError
from pytorrent_desktop.ui.main_window import MainWindow
from pytorrent_desktop.ui.models import Column


class FakeEngine:
    """Minimal stand-in for TorrentEngine's call surface used by MainWindow."""

    def __init__(self, torrents: list[TorrentStatus] | None = None) -> None:
        self._torrents = list(torrents or [])
        self.paused: list[str] = []
        self.resumed: list[str] = []
        self.removed: list[tuple[str, bool]] = []

    def snapshot(self) -> list[TorrentStatus]:
        return list(self._torrents)

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
