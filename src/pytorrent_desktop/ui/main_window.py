"""Main application window (docs/UX-SPEC.md §1).

Owns the 1-second poll timer that is the sole data path from
:class:`~pytorrent_desktop.core.engine.TorrentEngine` to the UI
(docs/ARCHITECTURE.md §4.2): nothing here calls into libtorrent directly, and
nothing in ``core/`` knows this window exists.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTableView,
    QToolBar,
    QToolButton,
)

from pytorrent_desktop.core.engine import TorrentEngine, TorrentStatus
from pytorrent_desktop.core.errors import EngineError
from pytorrent_desktop.ui.dialogs import AddTorrentDialog, RemoveDialog
from pytorrent_desktop.ui.models import TorrentTableModel, format_rate

_POLL_INTERVAL_MS = 1000
_ACTIVE_STATES = {"downloading", "seeding"}
_DEFAULT_SAVE_DIR_NAME = "pytorrent-desktop"


class MainWindow(QMainWindow):
    """Main window: toolbar + live torrent table + status bar (§1.1)."""

    def __init__(self, engine: TorrentEngine, parent=None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._default_save_path = str(Path.home() / "Downloads" / _DEFAULT_SAVE_DIR_NAME)

        self.setWindowTitle("pytorrent-desktop")
        self.resize(900, 500)

        self._model = TorrentTableModel(self)
        self._table_view = QTableView(self)
        self._table_view.setModel(self._model)
        self._table_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table_view.setSortingEnabled(False)
        self._table_view.horizontalHeader().setStretchLastSection(False)
        self._table_view.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self._table_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table_view.customContextMenuRequested.connect(self._show_context_menu)
        self.setCentralWidget(self._table_view)

        self._build_toolbar()
        self._status_bar = self.statusBar()
        # Connected only after the toolbar actions exist, since the handler
        # reads their enabled state.
        self._table_view.selectionModel().selectionChanged.connect(self._update_actions_enabled)
        self._update_actions_enabled()
        self._update_status_bar([])

        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(_POLL_INTERVAL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._poll_timer.start()
        # Populate immediately instead of waiting a full tick for first paint.
        self._poll()

    # -- toolbar ----------------------------------------------------------

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("메인 툴바", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        add_button = QToolButton(toolbar)
        add_button.setText("+ 추가")
        add_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        add_menu = QMenu(add_button)
        add_file_action = add_menu.addAction(".torrent 파일 열기…")
        add_file_action.triggered.connect(lambda: self._open_add_dialog(magnet=False))
        add_magnet_action = add_menu.addAction("Magnet 링크 추가…")
        add_magnet_action.triggered.connect(lambda: self._open_add_dialog(magnet=True))
        add_button.setMenu(add_menu)
        toolbar.addWidget(add_button)

        self._pause_action = toolbar.addAction("❚❚ 일시정지")
        self._pause_action.triggered.connect(self._pause_selected)
        self._resume_action = toolbar.addAction("▶ 재개")
        self._resume_action.triggered.connect(self._resume_selected)
        self._remove_action = toolbar.addAction("🗑 삭제")
        self._remove_action.triggered.connect(self._remove_selected)

    # -- polling ------------------------------------------------------------

    def _poll(self) -> None:
        snapshot = self._engine.snapshot()
        self._model.set_torrents(snapshot)
        self._update_status_bar(snapshot)
        self._update_actions_enabled()

    def _update_status_bar(self, snapshot: list[TorrentStatus]) -> None:
        total_down = sum(t.download_rate for t in snapshot)
        total_up = sum(t.upload_rate for t in snapshot)
        active = sum(
            1 for t in snapshot if not t.is_paused and not t.error and t.state in _ACTIVE_STATES
        )
        total = len(snapshot)
        self._status_bar.showMessage(
            f"전체: ↓ {format_rate(total_down)}  ↑ {format_rate(total_up)}   "
            f"활성 {active}/{total}"
        )

    # -- selection helpers ----------------------------------------------------

    def _selected_rows(self) -> list[TorrentStatus]:
        rows = {index.row() for index in self._table_view.selectionModel().selectedRows()}
        return [self._model.torrent_at(row) for row in sorted(rows)]

    def _update_actions_enabled(self) -> None:
        selected = self._selected_rows()
        self._pause_action.setEnabled(any(not t.is_paused for t in selected))
        self._resume_action.setEnabled(any(t.is_paused for t in selected))
        self._remove_action.setEnabled(bool(selected))

    def _show_context_menu(self, pos) -> None:
        index = self._table_view.indexAt(pos)
        if not index.isValid():
            return
        if not self._table_view.selectionModel().isRowSelected(index.row(), index.parent()):
            self._table_view.selectRow(index.row())

        menu = QMenu(self)
        pause_action = menu.addAction("일시정지")
        pause_action.setEnabled(self._pause_action.isEnabled())
        pause_action.triggered.connect(self._pause_selected)
        resume_action = menu.addAction("재개")
        resume_action.setEnabled(self._resume_action.isEnabled())
        resume_action.triggered.connect(self._resume_selected)
        menu.addSeparator()
        remove_action = menu.addAction("삭제…")
        remove_action.setEnabled(self._remove_action.isEnabled())
        remove_action.triggered.connect(self._remove_selected)
        menu.exec(self._table_view.viewport().mapToGlobal(pos))

    # -- actions --------------------------------------------------------------

    def _open_add_dialog(self, *, magnet: bool) -> None:
        dialog = AddTorrentDialog(default_save_path=self._default_save_path, parent=self)
        dialog.set_initial_tab(magnet)
        if dialog.exec() != AddTorrentDialog.DialogCode.Accepted:
            return

        save_path = dialog.save_path()
        self._default_save_path = save_path  # session-only default (UX-SPEC §2.4, OPEN-2)
        try:
            if dialog.is_magnet_mode():
                info_hash = self._engine.add_magnet(dialog.magnet_uri(), save_path)
            else:
                info_hash = self._engine.add_torrent_file(dialog.torrent_file_path(), save_path)
            if dialog.add_paused():
                self._engine.pause(info_hash)
        except EngineError as exc:
            self._show_error("토렌트를 추가할 수 없습니다", exc)
            return
        self._poll()

    def _pause_selected(self) -> None:
        for status in self._selected_rows():
            if status.is_paused:
                continue
            try:
                self._engine.pause(status.info_hash)
            except EngineError as exc:
                self._show_error("일시정지할 수 없습니다", exc)
        self._poll()

    def _resume_selected(self) -> None:
        for status in self._selected_rows():
            if not status.is_paused:
                continue
            try:
                self._engine.resume(status.info_hash)
            except EngineError as exc:
                self._show_error("재개할 수 없습니다", exc)
        self._poll()

    def _remove_selected(self) -> None:
        selected = self._selected_rows()
        if not selected:
            return
        dialog = RemoveDialog([status.name for status in selected], parent=self)
        if dialog.exec() != RemoveDialog.DialogCode.Accepted:
            return
        delete_data = dialog.delete_data()
        for status in selected:
            try:
                self._engine.remove(status.info_hash, delete_data=delete_data)
            except EngineError as exc:
                self._show_error("삭제할 수 없습니다", exc)
        self._poll()

    def _show_error(self, title: str, exc: Exception) -> None:
        QMessageBox.critical(self, title, str(exc))

    # -- lifecycle --------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override signature)
        self._poll_timer.stop()
        super().closeEvent(event)
