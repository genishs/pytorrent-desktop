"""Tests for :mod:`pytorrent_desktop.ui.models` (TorrentTableModel + formatting).

Uses hand-built :class:`TorrentStatus` fakes exclusively — no engine, no
libtorrent, no network — since the model only needs to know the dataclass
shape (docs/ARCHITECTURE.md §0's contract that the UI never has its own
state, only rendering).
"""

from __future__ import annotations

from PySide6.QtCore import Qt

from pytorrent_desktop.core.engine import TorrentStatus
from pytorrent_desktop.ui.models import (
    Column,
    TorrentTableModel,
    format_progress,
    format_rate,
    format_size,
    state_label,
)


def make_status(**overrides) -> TorrentStatus:
    defaults = dict(
        info_hash="a" * 40,
        name="ubuntu-24.04-desktop-amd64.iso",
        save_path="D:\\Downloads",
        total_bytes=5_800_000_000,
        downloaded_bytes=3_596_000_000,
        progress=0.62,
        download_rate=3_200_000,
        upload_rate=128_000,
        num_peers=14,
        num_seeds=3,
        state="downloading",
        is_paused=False,
        is_finished=False,
        queue_position=0,
        error=None,
    )
    defaults.update(overrides)
    return TorrentStatus(**defaults)


# -- formatting helpers -------------------------------------------------------


def test_format_size_bytes():
    assert format_size(512) == "512 B"


def test_format_size_kb():
    assert format_size(46_000) == "45 KB"


def test_format_size_mb():
    assert format_size(654_000_000) == "624 MB"


def test_format_size_gb():
    assert format_size(5_800_000_000) == "5.4 GB"


def test_format_size_zero_is_dash():
    assert format_size(0) == "-"


def test_format_rate_zero_is_dash():
    assert format_rate(0) == "-"


def test_format_rate_kb_per_sec():
    assert format_rate(3200) == "3.1 KB/s"


def test_format_progress_rounds_to_whole_percent():
    assert format_progress(0.615) == "62%" or format_progress(0.615) == "61%"
    assert format_progress(0.5) == "50%"
    assert format_progress(1.0) == "100%"


def test_state_label_error_takes_priority():
    status = make_status(state="downloading", is_paused=True, error="disk full")
    assert state_label(status) == "오류"


def test_state_label_paused_overrides_state():
    status = make_status(state="seeding", is_paused=True)
    assert state_label(status) == "일시정지"


def test_state_label_maps_known_states():
    assert state_label(make_status(state="downloading")) == "다운로드 중"
    assert state_label(make_status(state="seeding")) == "시딩 중"
    assert state_label(make_status(state="finished")) == "완료"
    assert state_label(make_status(state="fetching metadata")) == "메타데이터 수신 중"


def test_state_label_falls_back_to_raw_state_for_unknown_values():
    assert state_label(make_status(state="something_new")) == "something_new"


# -- TorrentTableModel --------------------------------------------------------


def test_empty_model_has_zero_rows():
    model = TorrentTableModel()
    assert model.rowCount() == 0
    assert model.columnCount() == len(Column)


def test_model_reports_rows_for_each_torrent():
    model = TorrentTableModel()
    model.set_torrents([make_status(info_hash="a" * 40), make_status(info_hash="b" * 40)])
    assert model.rowCount() == 2


def test_model_maps_columns_to_formatted_values():
    model = TorrentTableModel()
    status = make_status()
    model.set_torrents([status])

    def value(column: Column) -> str:
        return model.data(model.index(0, column), Qt.ItemDataRole.DisplayRole)

    assert value(Column.NAME) == status.name
    assert value(Column.SIZE) == format_size(status.total_bytes)
    assert value(Column.PROGRESS) == format_progress(status.progress)
    assert value(Column.DOWN_RATE) == format_rate(status.download_rate)
    assert value(Column.UP_RATE) == format_rate(status.upload_rate)
    assert value(Column.PEERS) == str(status.num_peers)
    assert value(Column.STATE) == state_label(status)


def test_model_shows_zero_peers_as_the_digit_zero_not_a_dash():
    model = TorrentTableModel()
    model.set_torrents([make_status(num_peers=0)])
    assert model.data(model.index(0, Column.PEERS), Qt.ItemDataRole.DisplayRole) == "0"


def test_set_torrents_same_keys_updates_in_place_without_reset():
    model = TorrentTableModel()
    status = make_status(download_rate=1000)
    model.set_torrents([status])

    reset_calls = []
    model.modelAboutToBeReset.connect(lambda: reset_calls.append(True))

    updated = make_status(download_rate=2000)
    model.set_torrents([updated])

    assert reset_calls == []
    assert model.data(model.index(0, Column.DOWN_RATE)) == format_rate(2000)


def test_set_torrents_different_keys_triggers_reset():
    model = TorrentTableModel()
    model.set_torrents([make_status(info_hash="a" * 40)])

    reset_calls = []
    model.modelReset.connect(lambda: reset_calls.append(True))

    model.set_torrents([make_status(info_hash="b" * 40)])

    assert reset_calls == [True]
    assert model.torrent_at(0).info_hash == "b" * 40


def test_header_data_returns_korean_labels():
    model = TorrentTableModel()
    assert model.headerData(Column.NAME, Qt.Orientation.Horizontal) == "이름"
    assert model.headerData(Column.STATE, Qt.Orientation.Horizontal) == "상태"
