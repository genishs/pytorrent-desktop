"""Main application window (docs/UX-SPEC.md §1).

Owns the 1-second poll timer that is the sole data path from
:class:`~pytorrent_desktop.core.engine.TorrentEngine` to the UI
(docs/ARCHITECTURE.md §4.2): nothing here calls into libtorrent directly, and
nothing in ``core/`` knows this window exists.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHeaderView,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTableView,
    QToolBar,
    QToolButton,
)

from pytorrent_desktop.core.config import (
    AppSettings,
    ConfigStore,
    OnCompleteSettings,
    ProxySettings,
    SearchSettings,
)
from pytorrent_desktop.core.engine import ProxyConfig, TorrentEngine, TorrentStatus
from pytorrent_desktop.core.errors import EngineError
from pytorrent_desktop.core.search.base import SearchProvider
from pytorrent_desktop.core.system_actions import request_system_shutdown
from pytorrent_desktop.ui.dialogs import (
    AddTorrentDialog,
    OnCompleteCountdownDialog,
    RemoveDialog,
    SearchConsentDialog,
    SearchDialog,
    SettingsDialog,
)
from pytorrent_desktop.ui.models import TorrentTableModel, format_rate

_POLL_INTERVAL_MS = 1000
_ACTIVE_STATES = {"downloading", "seeding"}
# docs/DECISIONS.md D3: 30s, cancellable, never skipped.
_ON_COMPLETE_COUNTDOWN_S = 30


def _default_search_provider_factory(search_settings: SearchSettings) -> SearchProvider:
    """Build the (only, for this alpha) built-in provider from current settings.

    Imported lazily inside the function (not at module top) so that merely
    importing ``ui.main_window`` never pulls in ``requests``/``bs4`` unless
    the user actually opens the search dialog — mirrors ``__main__.py``'s
    lazy-import pattern for the engine's native dependency.
    """
    from pytorrent_desktop.core.search.btdig import BtdigProvider

    return BtdigProvider(base_url=search_settings.btdig_base_url)


class MainWindow(QMainWindow):
    """Main window: toolbar + live torrent table + status bar (§1.1)."""

    def __init__(
        self,
        engine: TorrentEngine,
        *,
        config_store: ConfigStore | None = None,
        settings: AppSettings | None = None,
        system_shutdown_fn: Callable[[], None] = request_system_shutdown,
        search_provider_factory: Callable[
            [SearchSettings], SearchProvider
        ] = _default_search_provider_factory,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._search_provider_factory = search_provider_factory
        # ``config_store`` is optional so existing (and future) tests can
        # construct a MainWindow against a bare fake engine without wiring up
        # a real config.json — settings simply aren't persisted in that case.
        self._config_store = config_store
        self._settings = settings or AppSettings()
        self._system_shutdown_fn = system_shutdown_fn
        self._default_save_path = self._settings.default_save_path
        # SOCKS5 password (docs/DECISIONS.md D2): kept here, in memory, for
        # the lifetime of this window only — never written to config.json,
        # never read back from it. Re-prefills the Settings dialog if
        # reopened within the same run; blank again after a restart.
        self._proxy_password: str | None = None

        # docs/ARCHITECTURE.md §4.4 / docs/DECISIONS.md D3: tracks whether at
        # least one torrent has transitioned into "finished" *this session*
        # (as opposed to already being finished when restored from resume
        # data) and whether the countdown dialog is currently up, so the
        # main poll timer's own tick doesn't re-enter it.
        self._finished_seen: dict[str, bool] = {}
        self._any_completed_this_session = False
        self._countdown_active = False

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

        toolbar.addSeparator()
        # docs/ARCHITECTURE.md §6: toggles active_downloads=1 (one torrent
        # downloading at a time) vs. -1 (unlimited). Checked state follows
        # the loaded settings (defaults to True, matching
        # EngineConfig.sequential_queue's default).
        self._sequential_queue_action = toolbar.addAction("순차 다운로드")
        self._sequential_queue_action.setCheckable(True)
        self._sequential_queue_action.setChecked(self._settings.sequential_queue)
        self._sequential_queue_action.toggled.connect(self._toggle_sequential_queue)

        toolbar.addSeparator()
        # docs/ARCHITECTURE.md §9 / docs/SCOPE.md (v0.5.1a, EXPERIMENTAL/ALPHA):
        # only enabled once the user has turned search on in Settings — see
        # ``_update_search_action_enabled``.
        self._search_action = toolbar.addAction("🔍 검색 (알파)")
        self._search_action.triggered.connect(self._open_search_dialog)
        self._update_search_action_enabled()

        toolbar.addSeparator()
        settings_action = toolbar.addAction("⚙ 설정")
        settings_action.triggered.connect(self._open_settings_dialog)

    # -- polling ------------------------------------------------------------

    def _poll(self) -> None:
        snapshot = self._engine.snapshot()
        self._model.set_torrents(snapshot)
        self._update_status_bar(snapshot)
        self._update_actions_enabled()
        self._track_completions(snapshot)
        self._maybe_start_on_complete_countdown(snapshot)

    def _update_status_bar(self, snapshot: list[TorrentStatus]) -> None:
        total_down = sum(t.download_rate for t in snapshot)
        total_up = sum(t.upload_rate for t in snapshot)
        active = sum(
            1 for t in snapshot if not t.is_paused and not t.error and t.state in _ACTIVE_STATES
        )
        total = len(snapshot)
        self._status_bar.showMessage(
            f"전체: ↓ {format_rate(total_down)}  ↑ {format_rate(total_up)}   "
            f"활성 {active}/{total}   {self._proxy_status_text()}"
        )

    def _proxy_status_text(self) -> str:
        """docs/UX-SPEC.md §1.4's status-bar proxy indicator.

        This engine call (``privacy_status()``) only reports whether a
        proxy is currently *configured/applied*, not whether it's actually
        reachable — distinguishing "applied" from "applied but the
        connection failed" needs live network monitoring, which is out of
        this milestone's scope (see ``TorrentEngine.privacy_status``'s
        docstring for why that's also not something a headless test could
        verify anyway).
        """
        return (
            "프록시: ● 적용됨"
            if self._engine.privacy_status() == "enabled"
            else "프록시: 미설정"
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
        has_selection = bool(self._selected_rows())
        move_up_action = menu.addAction("위로 이동")
        move_up_action.setEnabled(has_selection)
        move_up_action.triggered.connect(lambda: self._move_selected("up"))
        move_down_action = menu.addAction("아래로 이동")
        move_down_action.setEnabled(has_selection)
        move_down_action.triggered.connect(lambda: self._move_selected("down"))
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

    def _move_selected(self, direction: str) -> None:
        for status in self._selected_rows():
            try:
                self._engine.move_in_queue(status.info_hash, direction)
            except EngineError as exc:
                self._show_error("순서를 변경할 수 없습니다", exc)
        self._poll()

    def _toggle_sequential_queue(self, checked: bool) -> None:
        self._engine.set_sequential_queue(checked)
        self._settings = replace(self._settings, sequential_queue=checked)
        self._save_settings()

    def _save_settings(self) -> None:
        if self._config_store is not None:
            self._config_store.save(self._settings)

    # -- settings dialog (docs/UX-SPEC.md §4) --------------------------------

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self._settings, initial_password=self._proxy_password, parent=self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return

        proxy_cfg: ProxyConfig | None = None
        if dialog.proxy_enabled():
            proxy_cfg = ProxyConfig(
                host=dialog.proxy_host(),
                port=dialog.proxy_port(),
                username=dialog.proxy_username(),
                password=dialog.proxy_password(),
                kill_switch=dialog.kill_switch(),
            )
        try:
            self._engine.configure_privacy(proxy_cfg)
            self._engine.set_listen_port(dialog.listen_port())
        except EngineError as exc:
            self._show_error("설정을 적용할 수 없습니다", exc)
            return

        self._proxy_password = dialog.proxy_password()
        self._settings = replace(
            self._settings,
            listen_port=dialog.listen_port(),
            default_save_path=dialog.default_save_path(),
            proxy=ProxySettings(
                enabled=dialog.proxy_enabled(),
                host=dialog.proxy_host(),
                port=dialog.proxy_port(),
                username=dialog.proxy_username(),
                kill_switch=dialog.kill_switch(),
            ),
            on_complete=OnCompleteSettings(action=dialog.on_complete_action()),
            search=SearchSettings(
                enabled=dialog.search_enabled(),
                btdig_base_url=dialog.search_btdig_base_url(),
                timeout=self._settings.search.timeout,
                consent_accepted=dialog.search_consent_accepted(),
            ),
        )
        self._default_save_path = self._settings.default_save_path
        self._save_settings()
        self._update_search_action_enabled()
        self._poll()

    # -- search (v0.5.1a, EXPERIMENTAL/ALPHA — docs/ARCHITECTURE.md §9, docs/SCOPE.md) ---

    def _update_search_action_enabled(self) -> None:
        self._search_action.setEnabled(self._settings.search.enabled)

    def _open_search_dialog(self) -> None:
        """Open the search dialog — gated on both "enabled" and consent.

        Even though the toolbar button is only enabled when
        ``search.enabled`` is true, this re-checks both conditions
        defensively (e.g. against a stale action or a settings change that
        raced the button's enabled state). Consent is checked *every* time
        this is invoked, not just once — ``_ensure_search_consent`` itself
        short-circuits to a no-op prompt when already accepted, so this
        never re-prompts once granted, but it also can never be bypassed by
        skipping straight to this method.
        """
        if not self._settings.search.enabled:
            return
        if not self._settings.search.consent_accepted and not self._ensure_search_consent():
            return

        provider = self._search_provider_factory(self._settings.search)
        dialog = SearchDialog(
            provider,
            timeout=self._settings.search.timeout,
            default_save_path=self._default_save_path,
            parent=self,
        )
        if dialog.exec() != SearchDialog.DialogCode.Accepted:
            return

        magnet = dialog.selected_magnet()
        save_path = dialog.selected_save_path()
        if not magnet or not save_path:
            return  # defensive: dialog only accepts with both set
        self._default_save_path = save_path
        try:
            self._engine.add_magnet(magnet, save_path)
        except EngineError as exc:
            self._show_error("토렌트를 추가할 수 없습니다", exc)
            return
        self._poll()

    def _ensure_search_consent(self) -> bool:
        """Legal-responsibility consent gate (backstop copy of the one in
        ``SettingsDialog``): blocks search — and therefore blocks any
        ``add_magnet`` call a search result could lead to — until the user
        explicitly agrees. Persists acceptance immediately so it isn't asked
        again next time. Returns whether the user agreed just now.
        """
        dialog = SearchConsentDialog(parent=self)
        if dialog.exec() != SearchConsentDialog.DialogCode.Accepted:
            return False
        self._settings = replace(
            self._settings, search=replace(self._settings.search, consent_accepted=True)
        )
        self._save_settings()
        return True

    # -- on-complete action (docs/DECISIONS.md D3, docs/ARCHITECTURE.md §4.4) ----

    def _track_completions(self, snapshot: list[TorrentStatus]) -> None:
        """Remember, per torrent, whether it has ever finished *this session*.

        A torrent that was already ``finished``/``seeding`` when restored
        from resume data at startup must not immediately arm the on-complete
        countdown — only a genuine not-finished -> finished transition
        *observed across two polls* counts (§4.4's "이번 세션에서 최소 하나가
        완료되었을 때"). That's why the very first time a given info-hash is
        seen it is only recorded, never treated as a transition — otherwise
        a torrent that's already finished on the very first poll tick after
        construction (the common "restored from resume data" case) would
        look identical to one that just completed.
        """
        current_hashes = {status.info_hash for status in snapshot}
        for status in snapshot:
            previously_seen = status.info_hash in self._finished_seen
            was_finished = self._finished_seen.get(status.info_hash, False)
            if previously_seen and status.is_finished and not was_finished:
                self._any_completed_this_session = True
            self._finished_seen[status.info_hash] = status.is_finished
        for stale_hash in set(self._finished_seen) - current_hashes:
            del self._finished_seen[stale_hash]

    def _maybe_start_on_complete_countdown(self, snapshot: list[TorrentStatus]) -> None:
        if self._countdown_active:
            return
        if self._settings.on_complete.action == "none":
            return
        if not self._any_completed_this_session:
            return
        if not snapshot or not all(status.is_finished for status in snapshot):
            return
        self._start_on_complete_countdown()

    def _start_on_complete_countdown(self) -> None:
        action = self._settings.on_complete.action
        action_description = (
            "시스템을 종료" if action == "shutdown_system" else "앱을 종료"
        )

        self._countdown_active = True
        self._poll_timer.stop()
        dialog = OnCompleteCountdownDialog(
            _ON_COMPLETE_COUNTDOWN_S,
            self._on_complete_still_eligible,
            action_description=action_description,
            parent=self,
        )
        result = dialog.exec()
        self._countdown_active = False

        if result == OnCompleteCountdownDialog.DialogCode.Accepted:
            # Tears down the engine (resume-data flush) and quits/shuts down
            # — do not touch the (now-closed) engine or restart the poll
            # timer afterwards.
            self._run_on_complete_action(action)
            return

        # Cancelled (manually, or auto-cancelled because a new, not-yet-
        # finished torrent showed up mid-countdown): don't retrigger until a
        # *new* completion happens (§5.6).
        self._any_completed_this_session = False
        self._poll_timer.start()
        self._poll()

    def _on_complete_still_eligible(self) -> bool:
        """Polled once per countdown tick: is "all finished" still true?"""
        snapshot = self._engine.snapshot()
        return bool(snapshot) and all(status.is_finished for status in snapshot)

    def _run_on_complete_action(self, action: str) -> None:
        """Execute the opted-in action once the countdown has run out.

        Resume data is always flushed first (docs/ARCHITECTURE.md §4.4) —
        required before an OS-level shutdown, and harmless/idempotent for a
        plain app quit (``__main__``'s own teardown would otherwise do it).
        The actual OS shutdown call goes through the injected
        ``system_shutdown_fn`` seam (docs/DECISIONS.md D3) — never invoked
        without having gone through the cancellable countdown above.
        """
        self._engine.shutdown()
        if action == "shutdown_system":
            self._system_shutdown_fn()
        app = QApplication.instance()
        if app is not None:
            app.quit()

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
