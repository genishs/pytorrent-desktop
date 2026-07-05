"""Qt table model that renders :class:`TorrentEngine` snapshots.

This module owns the only "presentation logic" allowed to know about
:class:`~pytorrent_desktop.core.engine.TorrentStatus` field names — it turns
each snapshot into the seven columns docs/UX-SPEC.md §1.3 describes (name,
size, progress, download rate, upload rate, peers, state) using
human-readable formatting. The model itself never talks to libtorrent or the
engine; :class:`MainWindow` is the only caller of ``set_torrents``.
"""

from __future__ import annotations

from enum import IntEnum

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from pytorrent_desktop.core.engine import TorrentStatus

_BINARY_KI = 1024
_BINARY_MI = 1024**2
_BINARY_GI = 1024**3


class Column(IntEnum):
    """Column indices for :class:`TorrentTableModel`, in display order."""

    NAME = 0
    SIZE = 1
    PROGRESS = 2
    DOWN_RATE = 3
    UP_RATE = 4
    PEERS = 5
    STATE = 6


_COLUMN_HEADERS = {
    Column.NAME: "이름",
    Column.SIZE: "크기",
    Column.PROGRESS: "진행률",
    Column.DOWN_RATE: "↓속도",
    Column.UP_RATE: "↑속도",
    Column.PEERS: "피어",
    Column.STATE: "상태",
}

# docs/UX-SPEC.md §5.1: engine state label -> list display label. Keys match
# core.engine._STATE_LABELS verbatim. `error` and `is_paused` take priority
# over this mapping (see `state_label` below).
_STATE_DISPLAY_LABELS = {
    "fetching metadata": "메타데이터 수신 중",
    "checking": "파일 확인 중",
    "checking resume data": "파일 확인 중",
    "downloading": "다운로드 중",
    "finished": "완료",
    "seeding": "시딩 중",
}

# "다운로드 중"인데 속도가 0인 경우의 세분화 라벨 (사용자가 진행률/속도가 전혀
# 안 움직여 "먹통"이라고 오해하는 것을 막기 위함 — 시더가 아예 없는 경우와,
# 피어는 있으나 아무 데이터도 못 받는 "정체" 상태를 구분해서 보여준다).
_LABEL_NO_SEEDS = "시더 없음"
_LABEL_STALLED = "정체"


def format_size(total_bytes: int) -> str:
    """Human-readable size (docs/UX-SPEC.md §1.3): B / KB / MB / GB.

    ``0`` (or negative, defensively) means "no size known yet" — e.g. a
    magnet torrent still fetching metadata — and renders as ``"-"``.
    """
    if total_bytes <= 0:
        return "-"
    if total_bytes < _BINARY_KI:
        return f"{total_bytes} B"
    if total_bytes < _BINARY_MI:
        return f"{total_bytes / _BINARY_KI:.0f} KB"
    if total_bytes < _BINARY_GI:
        return f"{total_bytes / _BINARY_MI:.0f} MB"
    return f"{total_bytes / _BINARY_GI:.1f} GB"


def format_rate(bytes_per_sec: int) -> str:
    """Human-readable transfer rate; ``0`` renders as ``"-"`` (§1.3)."""
    if bytes_per_sec <= 0:
        return "-"
    if bytes_per_sec < _BINARY_MI:
        return f"{bytes_per_sec / _BINARY_KI:.1f} KB/s"
    return f"{bytes_per_sec / _BINARY_MI:.1f} MB/s"


def format_progress(progress: float) -> str:
    """Progress as a rounded percentage, e.g. ``62%`` (§1.3, no decimals)."""
    return f"{round(progress * 100)}%"


def _has_no_seeds(status: TorrentStatus) -> bool:
    """True if there is no known seed anywhere — connected or in the swarm.

    ``num_seeds`` is peers-we're-connected-to; ``num_complete`` is the
    tracker/DHT scrape's swarm-wide seed count, or ``-1`` if libtorrent
    hasn't got scrape info yet (verified libtorrent 2.0.13 sentinel — *not*
    "zero seeds"). When the swarm-wide count is unknown, connected-seed count
    alone is the best signal available.
    """
    if status.num_seeds > 0:
        return False
    return status.num_complete <= 0


def state_label(status: TorrentStatus) -> str:
    """Map a snapshot to its list-view state label per docs/UX-SPEC.md §5.1.

    Priority: error > paused > the underlying engine state (falling back to
    the raw engine string for any state this UI doesn't special-case yet).

    Within "downloading", a zero download rate on an unfinished torrent is
    further split into "시더 없음" (no seed connected or known in the swarm)
    vs. "정체" (peers are there, but nothing is coming through) — otherwise a
    seedless torrent just sits at "다운로드 중" with 0%/0 B/s forever, which
    reads as the app being stuck rather than as "there's genuinely nobody to
    download from yet".
    """
    if status.error:
        return "오류"
    if status.is_paused:
        return "일시정지"
    if status.state == "downloading" and not status.is_finished and status.download_rate == 0:
        return _LABEL_NO_SEEDS if _has_no_seeds(status) else _LABEL_STALLED
    return _STATE_DISPLAY_LABELS.get(status.state, status.state)


class TorrentTableModel(QAbstractTableModel):
    """Read-only table model driven by ``list[TorrentStatus]`` snapshots.

    ``set_torrents`` is called ~1x/sec by :class:`MainWindow`'s poll timer
    (docs/ARCHITECTURE.md §4.2). When the same torrents are present in the
    same order (the common case — nothing added/removed since the last
    tick), it emits ``dataChanged`` in place so the view keeps the current
    selection; only an actual membership/order change triggers a full model
    reset.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[TorrentStatus] = []

    # -- population ----------------------------------------------------

    def set_torrents(self, torrents: list[TorrentStatus]) -> None:
        old_keys = [row.info_hash for row in self._rows]
        new_keys = [row.info_hash for row in torrents]
        if old_keys == new_keys:
            self._rows = torrents
            if torrents:
                top_left = self.index(0, 0)
                bottom_right = self.index(len(torrents) - 1, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right)
            return
        self.beginResetModel()
        self._rows = torrents
        self.endResetModel()

    def torrent_at(self, row: int) -> TorrentStatus:
        return self._rows[row]

    # -- QAbstractTableModel overrides ----------------------------------

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        if parent.isValid():
            return 0
        return len(Column)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return _COLUMN_HEADERS.get(Column(section), "")
        return str(section + 1)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._rows)):
            return None
        status = self._rows[index.row()]
        column = Column(index.column())

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display_value(status, column)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            return self._alignment(column)
        if role == Qt.ItemDataRole.ToolTipRole and column == Column.NAME:
            return status.name
        return None

    @staticmethod
    def _display_value(status: TorrentStatus, column: Column) -> str:
        if column == Column.NAME:
            return status.name
        if column == Column.SIZE:
            return format_size(status.total_bytes)
        if column == Column.PROGRESS:
            return format_progress(status.progress)
        if column == Column.DOWN_RATE:
            return format_rate(status.download_rate)
        if column == Column.UP_RATE:
            return format_rate(status.upload_rate)
        if column == Column.PEERS:
            return str(status.num_peers)
        if column == Column.STATE:
            return state_label(status)
        return ""

    @staticmethod
    def _alignment(column: Column) -> int:
        if column in (Column.SIZE, Column.DOWN_RATE, Column.UP_RATE):
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if column in (Column.PROGRESS, Column.PEERS, Column.STATE):
            return int(Qt.AlignmentFlag.AlignCenter)
        return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
