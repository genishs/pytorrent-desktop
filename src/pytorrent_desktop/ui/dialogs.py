"""Add-torrent, remove-confirmation, settings, and on-complete-countdown
dialogs (docs/UX-SPEC.md §2, §3, §4, §5.6).

All dialogs only collect input; they never call into
:class:`~pytorrent_desktop.core.engine.TorrentEngine` themselves — that stays
in :class:`~pytorrent_desktop.ui.main_window.MainWindow`, which is the only
place engine errors are caught and turned into user-facing messages.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pytorrent_desktop.core.config import AppSettings
from pytorrent_desktop.core.errors import SearchError
from pytorrent_desktop.core.search.base import SearchProvider, SearchResult
from pytorrent_desktop.ui.models import format_size

# docs/UX-SPEC.md §2.3: real-time inline validation gates the Add button.
# Matches the documented prefix; a v2/hybrid ("btmh") magnet is accepted too
# since the engine parses both (docs/ARCHITECTURE.md §3.5).
_MAGNET_PATTERN = re.compile(r"^magnet:\?xt=urn:bt(ih|mh):[0-9A-Za-z]+", re.IGNORECASE)


def is_valid_magnet(uri: str) -> bool:
    return bool(_MAGNET_PATTERN.match(uri.strip()))


class AddTorrentDialog(QDialog):
    """Add-torrent dialog: ``.torrent`` file tab + magnet-link tab (§2.1).

    Common fields (save path, "add paused") live below the tabs and are
    shared by both input modes.
    """

    FILE_TAB = 0
    MAGNET_TAB = 1

    def __init__(self, default_save_path: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("토렌트 추가")
        self.setModal(True)

        self._tabs = QTabWidget(self)
        self._tabs.addTab(self._build_file_tab(), ".torrent 파일")
        self._tabs.addTab(self._build_magnet_tab(), "Magnet 링크")
        self._tabs.currentChanged.connect(self._update_add_enabled)

        self.save_path_edit = QLineEdit(default_save_path, self)
        save_path_browse = QPushButton("찾아보기", self)
        save_path_browse.clicked.connect(self._browse_save_path)
        save_path_row = QHBoxLayout()
        save_path_row.addWidget(self.save_path_edit)
        save_path_row.addWidget(save_path_browse)

        self.add_paused_checkbox = QCheckBox("일시정지 상태로 추가", self)

        common_form = QFormLayout()
        common_form.addRow("저장 경로:", save_path_row)
        common_form.addRow("", self.add_paused_checkbox)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("추가")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._tabs)
        layout.addLayout(common_form)
        layout.addWidget(self._buttons)

        self.save_path_edit.textChanged.connect(self._update_add_enabled)
        self._update_add_enabled()

    # -- tab construction ------------------------------------------------

    def _build_file_tab(self) -> QWidget:
        tab = QWidget(self)
        self.file_path_edit = QLineEdit(tab)
        browse_button = QPushButton("찾아보기", tab)
        browse_button.clicked.connect(self._browse_torrent_file)
        self.file_error_label = QLabel(tab)
        self.file_error_label.setVisible(False)

        row = QHBoxLayout()
        row.addWidget(self.file_path_edit)
        row.addWidget(browse_button)

        layout = QVBoxLayout(tab)
        layout.addLayout(row)
        layout.addWidget(self.file_error_label)
        self.file_path_edit.textChanged.connect(self._update_add_enabled)
        return tab

    def _build_magnet_tab(self) -> QWidget:
        tab = QWidget(self)
        self.magnet_edit = QLineEdit(tab)
        self.magnet_error_label = QLabel("유효한 magnet 링크가 아닙니다", tab)
        self.magnet_error_label.setStyleSheet("color: red;")
        self.magnet_error_label.setVisible(False)
        paste_button = QPushButton("클립보드에서 붙여넣기", tab)
        paste_button.clicked.connect(self._paste_from_clipboard)

        layout = QVBoxLayout(tab)
        layout.addWidget(self.magnet_edit)
        layout.addWidget(self.magnet_error_label)
        layout.addWidget(paste_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.magnet_edit.textChanged.connect(self._update_add_enabled)
        return tab

    # -- actions ----------------------------------------------------------

    def _browse_torrent_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "torrent 파일 선택", "", "Torrent Files (*.torrent)"
        )
        if path:
            self.file_path_edit.setText(path)

    def _browse_save_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "저장 경로 선택", self.save_path_edit.text()
        )
        if directory:
            self.save_path_edit.setText(directory)

    def _paste_from_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if is_valid_magnet(text):
            self.magnet_edit.setText(text)
        else:
            self.magnet_error_label.setText("클립보드에 magnet 링크가 없습니다")
            self.magnet_error_label.setVisible(True)

    # -- validation ---------------------------------------------------------

    def _update_add_enabled(self) -> None:
        save_path_ok = bool(self.save_path_edit.text().strip())
        if self._tabs.currentIndex() == self.FILE_TAB:
            file_path = self.file_path_edit.text().strip()
            file_ok = bool(file_path) and Path(file_path).is_file()
            ok = file_ok and save_path_ok
        else:
            magnet_text = self.magnet_edit.text()
            magnet_ok = is_valid_magnet(magnet_text)
            self.magnet_error_label.setText("유효한 magnet 링크가 아닙니다")
            self.magnet_error_label.setVisible(bool(magnet_text) and not magnet_ok)
            ok = magnet_ok and save_path_ok
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ok)

    # -- result accessors (read after exec() returns Accepted) ---------------

    def is_magnet_mode(self) -> bool:
        return self._tabs.currentIndex() == self.MAGNET_TAB

    def torrent_file_path(self) -> str:
        return self.file_path_edit.text().strip()

    def magnet_uri(self) -> str:
        return self.magnet_edit.text().strip()

    def save_path(self) -> str:
        return self.save_path_edit.text().strip()

    def add_paused(self) -> bool:
        return self.add_paused_checkbox.isChecked()

    def set_initial_tab(self, magnet: bool) -> None:
        self._tabs.setCurrentIndex(self.MAGNET_TAB if magnet else self.FILE_TAB)


class RemoveDialog(QDialog):
    """Remove-confirmation dialog (docs/UX-SPEC.md §3).

    Defaults to the safe "list only" option so accidental data loss requires
    an explicit extra click to opt into ``delete_data``.
    """

    _MAX_LISTED_NAMES = 5

    def __init__(self, torrent_names: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("토렌트 삭제")
        self.setModal(True)

        count = len(torrent_names)
        summary = QLabel(f"선택한 {count}개 항목을 삭제합니다:", self)

        shown_names = torrent_names[: self._MAX_LISTED_NAMES]
        lines = [f"  • {name}" for name in shown_names]
        remaining = count - len(shown_names)
        if remaining > 0:
            lines.append(f"  외 {remaining}개")
        names_label = QLabel("\n".join(lines), self)

        self.keep_data_radio = QRadioButton("목록에서만 제거", self)
        keep_data_hint = QLabel("내려받은 파일은 디스크에 그대로 남습니다.", self)
        self.delete_data_radio = QRadioButton("데이터까지 삭제", self)
        delete_data_hint = QLabel(
            "⚠ 디스크의 파일도 함께 삭제됩니다. 이 작업은 되돌릴 수 없습니다.", self
        )
        delete_data_hint.setStyleSheet("color: red;")

        # Safe default: never pre-select the destructive option.
        self.keep_data_radio.setChecked(True)
        self.delete_data_radio.toggled.connect(self._update_button_label)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        self._delete_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._delete_button.setText("삭제")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(summary)
        layout.addWidget(names_label)
        layout.addWidget(self.keep_data_radio)
        layout.addWidget(keep_data_hint)
        layout.addWidget(self.delete_data_radio)
        layout.addWidget(delete_data_hint)
        layout.addWidget(self._buttons)

    def _update_button_label(self, delete_checked: bool) -> None:
        self._delete_button.setText("영구 삭제" if delete_checked else "삭제")

    def delete_data(self) -> bool:
        return self.delete_data_radio.isChecked()


# -- Settings dialog (docs/UX-SPEC.md §4) ------------------------------------

_MIN_LISTEN_PORT = 1024
_MAX_LISTEN_PORT = 65535
_MIN_PROXY_PORT = 1
_MAX_PROXY_PORT = 65535

_KILL_SWITCH_WARNING = "프록시 연결이 끊기면 실제 IP로 직접 연결될 수 있습니다."
_ON_COMPLETE_HINT = (
    "모든 다운로드가 끝나면 자동으로 실행됩니다. "
    "실행 전 취소할 수 있는 확인 창이 표시됩니다."
)

# -- search (v0.5.1a, EXPERIMENTAL/ALPHA) legal notice ------------------------
#
# Shown (a) unconditionally at the top of SearchDialog every time it opens,
# and (b) inside SearchConsentDialog as the thing the user must explicitly
# agree to before search is ever used (docs/SCOPE.md, docs/ARCHITECTURE.md
# §9). Korean primary, English secondary — must state: (1) this feature can
# be legally problematic, (2) downloaded software/content may violate its
# license, (3) the user bears all responsibility.
_SEARCH_LEGAL_NOTICE = (
    "⚠ 실험적 기능(알파): 검색은 btdig 등 제3자 사이트에 질의를 보냅니다. "
    "이 기능(토렌트 검색/다운로드)의 사용은 관할 법률에 따라 법적으로 문제가 될 수 있으며, "
    "다운로드하는 소프트웨어/콘텐츠가 해당 라이선스를 위반할 수 있습니다. "
    "검색 결과 확인 및 다운로드에 대한 모든 책임은 사용자 본인에게 있습니다.\n\n"
    "Experimental (alpha) feature: search sends queries to third-party sites "
    "such as btdig. Use of this torrent search/download feature may be "
    "illegal depending on your jurisdiction, and the software/content you "
    "download may violate its license. You are solely responsible for any "
    "search results you act on and anything you download."
)

_SEARCH_CONSENT_CHECKBOX_TEXT = (
    "위 내용을 읽고 이해했으며, 이에 대한 책임은 나에게 있음에 동의합니다."
    " (I have read and understood the above, and I accept sole responsibility.)"
)


class SettingsDialog(QDialog):
    """Settings dialog: save path, listening port, SOCKS5 proxy + kill
    switch, on-complete action (docs/UX-SPEC.md §4).

    Like the other dialogs, this only collects input — :class:`MainWindow`
    is responsible for calling ``TorrentEngine.configure_privacy``/
    ``set_listen_port`` and ``ConfigStore.save`` after ``exec()`` returns
    ``Accepted``.

    The password field is **never** pre-filled from disk (docs/DECISIONS.md
    D2 — ``AppSettings``/``ProxySettings`` has no password field to begin
    with). ``initial_password`` lets the caller re-populate it from
    whatever the user typed earlier *in this run* (kept in memory by
    ``MainWindow``, never written to ``config.json``), so reopening this
    dialog within the same session doesn't force retyping it, but a fresh
    app start always starts blank.
    """

    def __init__(
        self,
        settings: AppSettings,
        *,
        initial_password: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("설정")
        self.setModal(True)

        general_group = self._build_general_group(settings)
        privacy_group = self._build_privacy_group(settings, initial_password)
        on_complete_group = self._build_on_complete_group(settings)
        search_group = self._build_search_group(settings)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self
        )
        self._buttons.button(QDialogButtonBox.StandardButton.Ok).setText("저장")
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        self._buttons.accepted.connect(self._on_save_clicked)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(general_group)
        layout.addWidget(privacy_group)
        layout.addWidget(on_complete_group)
        layout.addWidget(search_group)
        layout.addStretch(1)
        layout.addWidget(self._buttons)

        self._update_proxy_fields_enabled(self.proxy_enabled_checkbox.isChecked())
        self._update_kill_switch_warning()
        self._update_on_complete_hint()
        self._update_search_fields_enabled(self.search_enabled_checkbox.isChecked())

    # -- construction ------------------------------------------------------

    def _build_general_group(self, settings: AppSettings) -> QGroupBox:
        self.save_path_edit = QLineEdit(settings.default_save_path, self)
        save_path_browse = QPushButton("찾아보기", self)
        save_path_browse.clicked.connect(self._browse_save_path)
        save_path_row = QHBoxLayout()
        save_path_row.addWidget(self.save_path_edit)
        save_path_row.addWidget(save_path_browse)
        self.save_path_error_label = QLabel(self)
        self.save_path_error_label.setProperty("role", "error")
        self.save_path_error_label.setVisible(False)

        self.listen_port_edit = QLineEdit(str(settings.listen_port), self)
        self.listen_port_error_label = QLabel(self)
        self.listen_port_error_label.setProperty("role", "error")
        self.listen_port_error_label.setVisible(False)

        group = QGroupBox("일반", self)
        form = QFormLayout(group)
        form.addRow("기본 저장 경로:", save_path_row)
        form.addRow("", self.save_path_error_label)
        form.addRow("리스닝 포트:", self.listen_port_edit)
        form.addRow("", self.listen_port_error_label)
        return group

    def _build_privacy_group(
        self, settings: AppSettings, initial_password: str | None
    ) -> QGroupBox:
        proxy = settings.proxy
        self.proxy_enabled_checkbox = QCheckBox("프록시 사용", self)
        self.proxy_enabled_checkbox.setChecked(proxy.enabled)
        self.proxy_enabled_checkbox.toggled.connect(self._update_proxy_fields_enabled)

        self.proxy_host_edit = QLineEdit(proxy.host, self)
        self.proxy_port_edit = QLineEdit(str(proxy.port), self)
        self.proxy_username_edit = QLineEdit(proxy.username or "", self)
        self.proxy_password_edit = QLineEdit(initial_password or "", self)
        self.proxy_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        for edit in (self.proxy_host_edit, self.proxy_port_edit):
            edit.textChanged.connect(self._clear_proxy_error)

        host_port_row = QHBoxLayout()
        host_port_row.addWidget(QLabel("호스트:", self))
        host_port_row.addWidget(self.proxy_host_edit)
        host_port_row.addWidget(QLabel("포트:", self))
        host_port_row.addWidget(self.proxy_port_edit)

        self.kill_switch_checkbox = QCheckBox(
            "Kill switch (프록시 끊기면 직접 연결 차단)", self
        )
        self.kill_switch_checkbox.setChecked(proxy.kill_switch)
        self.kill_switch_checkbox.toggled.connect(self._update_kill_switch_warning)
        self.kill_switch_warning_label = QLabel(_KILL_SWITCH_WARNING, self)
        self.kill_switch_warning_label.setProperty("role", "warning")
        self.kill_switch_warning_label.setWordWrap(True)

        self.proxy_error_label = QLabel(self)
        self.proxy_error_label.setProperty("role", "error")
        self.proxy_error_label.setVisible(False)

        form = QFormLayout()
        form.addRow(host_port_row)
        form.addRow("사용자:", self.proxy_username_edit)
        form.addRow("비밀번호:", self.proxy_password_edit)

        group = QGroupBox("프라이버시 — SOCKS5 프록시", self)
        layout = QVBoxLayout(group)
        layout.addWidget(self.proxy_enabled_checkbox)
        layout.addLayout(form)
        layout.addWidget(self.kill_switch_checkbox)
        layout.addWidget(self.kill_switch_warning_label)
        layout.addWidget(self.proxy_error_label)
        return group

    def _build_on_complete_group(self, settings: AppSettings) -> QGroupBox:
        self.on_complete_none_radio = QRadioButton("없음", self)
        self.on_complete_quit_radio = QRadioButton("앱 종료", self)
        self.on_complete_shutdown_radio = QRadioButton("시스템 종료", self)
        radio_by_action = {
            "none": self.on_complete_none_radio,
            "quit_app": self.on_complete_quit_radio,
            "shutdown_system": self.on_complete_shutdown_radio,
        }
        radio_by_action[settings.on_complete.action].setChecked(True)
        for radio in radio_by_action.values():
            radio.toggled.connect(self._update_on_complete_hint)

        self.on_complete_hint_label = QLabel(_ON_COMPLETE_HINT, self)
        self.on_complete_hint_label.setProperty("role", "hint")
        self.on_complete_hint_label.setWordWrap(True)

        group = QGroupBox("완료 후 동작", self)
        layout = QVBoxLayout(group)
        for radio in radio_by_action.values():
            layout.addWidget(radio)
        layout.addWidget(self.on_complete_hint_label)
        return group

    def _build_search_group(self, settings: AppSettings) -> QGroupBox:
        """검색 탭 (v0.5.1a, EXPERIMENTAL/ALPHA): enable toggle + btdig base URL.

        Toggling the checkbox *on* while the legal-responsibility consent
        (``SearchSettings.consent_accepted``) hasn't been granted yet pops the
        consent gate (``SearchConsentDialog``) right here, inline — one of
        the two trigger points the product spec calls for, the other being
        ``MainWindow._ensure_search_consent`` guarding the search dialog
        itself as a defense-in-depth backstop (e.g. against a hand-edited
        ``config.json`` with ``enabled: true`` but no consent recorded).
        Declining reverts the checkbox to unchecked.
        """
        search = settings.search
        # Tracks whether consent has been granted *in this dialog session*
        # (seeded from the persisted value, then possibly flipped true by
        # the gate below) — read back by ``search_consent_accepted()``.
        self._search_consent_accepted = search.consent_accepted

        self.search_enabled_checkbox = QCheckBox("검색 사용 (실험적/알파)", self)
        self.search_enabled_checkbox.setChecked(search.enabled)

        self.search_base_url_edit = QLineEdit(search.btdig_base_url, self)
        self.search_base_url_edit.textChanged.connect(self._clear_search_error)
        self.search_error_label = QLabel(self)
        self.search_error_label.setProperty("role", "error")
        self.search_error_label.setVisible(False)

        self.search_legal_label = QLabel(_SEARCH_LEGAL_NOTICE, self)
        self.search_legal_label.setProperty("role", "warning")
        self.search_legal_label.setWordWrap(True)

        # Connected only now, after the initial setChecked() above, so
        # pre-filling the checkbox from already-saved settings can never
        # itself pop the consent-gate dialog during construction.
        self.search_enabled_checkbox.toggled.connect(self._on_search_enabled_toggled)

        form = QFormLayout()
        form.addRow("btdig base URL:", self.search_base_url_edit)
        form.addRow("", self.search_error_label)

        group = QGroupBox("검색 (실험적/알파)", self)
        layout = QVBoxLayout(group)
        layout.addWidget(self.search_enabled_checkbox)
        layout.addWidget(self.search_legal_label)
        layout.addLayout(form)
        return group

    # -- dynamic field state -------------------------------------------------

    def _update_proxy_fields_enabled(self, enabled: bool) -> None:
        for widget in (
            self.proxy_host_edit,
            self.proxy_port_edit,
            self.proxy_username_edit,
            self.proxy_password_edit,
            self.kill_switch_checkbox,
        ):
            widget.setEnabled(enabled)
        self._update_kill_switch_warning()

    def _update_kill_switch_warning(self) -> None:
        show = self.proxy_enabled_checkbox.isChecked() and not self.kill_switch_checkbox.isChecked()
        self.kill_switch_warning_label.setVisible(show)

    def _update_on_complete_hint(self) -> None:
        self.on_complete_hint_label.setVisible(not self.on_complete_none_radio.isChecked())

    def _clear_proxy_error(self) -> None:
        self.proxy_error_label.setVisible(False)

    def _update_search_fields_enabled(self, enabled: bool) -> None:
        self.search_base_url_edit.setEnabled(enabled)

    def _on_search_enabled_toggled(self, checked: bool) -> None:
        self._update_search_fields_enabled(checked)
        if checked and not self._search_consent_accepted:
            if self._run_search_consent_gate():
                self._search_consent_accepted = True
            else:
                # Declined: revert. This re-enters this handler with
                # checked=False, which is a no-op past this branch.
                self.search_enabled_checkbox.setChecked(False)
                return
        self._clear_search_error()

    def _run_search_consent_gate(self) -> bool:
        """Show the consent gate; return whether the user agreed.

        Split out as its own method (rather than inlined) purely so tests
        can monkeypatch it to skip the modal dialog while still exercising
        the enable/revert wiring around it.
        """
        dialog = SearchConsentDialog(parent=self)
        return dialog.exec() == SearchConsentDialog.DialogCode.Accepted

    def _clear_search_error(self) -> None:
        self.search_error_label.setVisible(False)

    def _browse_save_path(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "저장 경로 선택", self.save_path_edit.text()
        )
        if directory:
            self.save_path_edit.setText(directory)

    # -- validation + accept -------------------------------------------------

    def _on_save_clicked(self) -> None:
        if self._validate():
            self.accept()

    def _validate(self) -> bool:
        ok = True
        self.save_path_error_label.setVisible(False)
        self.listen_port_error_label.setVisible(False)
        self.proxy_error_label.setVisible(False)
        self.search_error_label.setVisible(False)

        ok = self._validate_save_path() and ok
        ok = self._validate_listen_port() and ok
        if self.proxy_enabled_checkbox.isChecked():
            ok = self._validate_proxy_fields() and ok
        if self.search_enabled_checkbox.isChecked():
            ok = self._validate_search_fields() and ok
        return ok

    def _validate_save_path(self) -> bool:
        text = self.save_path_edit.text().strip()
        if not text:
            self.save_path_error_label.setText("저장 경로를 입력하세요")
            self.save_path_error_label.setVisible(True)
            return False
        path = Path(text)
        if not path.is_dir():
            try:
                path.mkdir(parents=True, exist_ok=True)
            except OSError:
                self.save_path_error_label.setText("이 경로에 쓸 수 없습니다")
                self.save_path_error_label.setVisible(True)
                return False
        if not os.access(path, os.W_OK):
            self.save_path_error_label.setText("이 경로에 쓸 수 없습니다")
            self.save_path_error_label.setVisible(True)
            return False
        return True

    def _validate_listen_port(self) -> bool:
        try:
            port = int(self.listen_port_edit.text().strip())
            if not (_MIN_LISTEN_PORT <= port <= _MAX_LISTEN_PORT):
                raise ValueError
        except ValueError:
            self.listen_port_error_label.setText(
                f"{_MIN_LISTEN_PORT}-{_MAX_LISTEN_PORT} 범위로 입력하세요"
            )
            self.listen_port_error_label.setVisible(True)
            return False
        return True

    def _validate_proxy_fields(self) -> bool:
        host = self.proxy_host_edit.text().strip()
        if not host:
            self.proxy_error_label.setText("호스트를 입력하세요")
            self.proxy_error_label.setVisible(True)
            return False
        try:
            port = int(self.proxy_port_edit.text().strip())
            if not (_MIN_PROXY_PORT <= port <= _MAX_PROXY_PORT):
                raise ValueError
        except ValueError:
            self.proxy_error_label.setText("유효한 포트를 입력하세요")
            self.proxy_error_label.setVisible(True)
            return False
        return True

    def _validate_search_fields(self) -> bool:
        base_url = self.search_base_url_edit.text().strip()
        if not base_url:
            self.search_error_label.setText("btdig base URL을 입력하세요")
            self.search_error_label.setVisible(True)
            return False
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            self.search_error_label.setText("http:// 또는 https://로 시작해야 합니다")
            self.search_error_label.setVisible(True)
            return False
        return True

    # -- result accessors (read after exec() returns Accepted) ---------------

    def default_save_path(self) -> str:
        return self.save_path_edit.text().strip()

    def listen_port(self) -> int:
        return int(self.listen_port_edit.text().strip())

    def proxy_enabled(self) -> bool:
        return self.proxy_enabled_checkbox.isChecked()

    def proxy_host(self) -> str:
        return self.proxy_host_edit.text().strip()

    def proxy_port(self) -> int:
        return int(self.proxy_port_edit.text().strip())

    def proxy_username(self) -> str | None:
        return self.proxy_username_edit.text().strip() or None

    def proxy_password(self) -> str | None:
        return self.proxy_password_edit.text() or None

    def kill_switch(self) -> bool:
        return self.kill_switch_checkbox.isChecked()

    def on_complete_action(self) -> str:
        if self.on_complete_quit_radio.isChecked():
            return "quit_app"
        if self.on_complete_shutdown_radio.isChecked():
            return "shutdown_system"
        return "none"

    def search_enabled(self) -> bool:
        return self.search_enabled_checkbox.isChecked()

    def search_btdig_base_url(self) -> str:
        return self.search_base_url_edit.text().strip()

    def search_consent_accepted(self) -> bool:
        """Whether the legal-responsibility gate has been accepted, either
        previously (persisted) or just now via the inline consent gate this
        dialog ran when the checkbox was toggled on (§ ``_on_search_enabled_toggled``)."""
        return self._search_consent_accepted


# -- On-complete countdown dialog (docs/DECISIONS.md D3, docs/UX-SPEC.md §5.6) -----


class OnCompleteCountdownDialog(QDialog):
    """Cancellable countdown shown before the opted-in on-complete action runs.

    ``still_eligible`` is polled once per tick (alongside the visible
    countdown): if it returns ``False`` — e.g. a new torrent was added
    mid-countdown and the "all finished" condition no longer holds — the
    dialog auto-cancels exactly like a manual "지금 취소" click (§5.6: "카운트
    다운 중 새 토렌트가 추가되어 완료가 아닌 상태가 생기면 자동으로 다이얼로그
    취소"). Either way the dialog is rejected; only a countdown that runs out
    on its own accepts.

    ``interval_ms`` defaults to the real 1-second tick but is overridable so
    tests can exercise the full countdown/cancel/expire behavior quickly
    without waiting out a real 30-second timer.
    """

    def __init__(
        self,
        seconds: int,
        still_eligible: Callable[[], bool],
        *,
        action_description: str = "시스템을 종료",
        interval_ms: int = 1000,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("모든 다운로드 완료")
        self.setModal(True)
        self._still_eligible = still_eligible
        self._action_description = action_description
        self._remaining = seconds

        self._message_label = QLabel(self)
        cancel_button = QPushButton("지금 취소", self)
        cancel_button.clicked.connect(self._cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self._message_label)
        layout.addWidget(cancel_button, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._tick)

        self._update_message()

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override signature)
        super().showEvent(event)
        self._timer.start()

    def remaining_seconds(self) -> int:
        return self._remaining

    def _tick(self) -> None:
        if not self._still_eligible():
            self._cancel()
            return
        self._remaining -= 1
        if self._remaining <= 0:
            self._timer.stop()
            self.accept()
            return
        self._update_message()

    def _update_message(self) -> None:
        self._message_label.setText(f"{self._remaining}초 후 {self._action_description}합니다.")

    def _cancel(self) -> None:
        self._timer.stop()
        self.reject()


# -- Search consent gate (v0.5.1a, EXPERIMENTAL/ALPHA) ------------------------


class SearchConsentDialog(QDialog):
    """Legal-responsibility consent gate for the experimental search feature.

    Must be explicitly accepted (checkbox checked *and* the "동의" button
    clicked) before a search provider is ever queried or a search result is
    ever added via ``TorrentEngine.add_magnet``. Two call sites enforce this:
    ``SettingsDialog`` pops it the moment the user toggles "검색 사용" on
    (if not already consented), and ``MainWindow._ensure_search_consent``
    pops it again as a backstop right before the search dialog opens (in
    case search got enabled without going through the Settings toggle, e.g.
    a hand-edited ``config.json``). Declining (Cancel, or closing the
    dialog) must leave search blocked — callers check ``exec()``'s result
    and must not proceed on anything but ``Accepted``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("검색 기능 사용 동의 (실험적/알파)")
        self.setModal(True)

        notice_label = QLabel(_SEARCH_LEGAL_NOTICE, self)
        notice_label.setWordWrap(True)
        notice_label.setProperty("role", "warning")

        self.consent_checkbox = QCheckBox(_SEARCH_CONSENT_CHECKBOX_TEXT, self)
        self.consent_checkbox.toggled.connect(self._update_agree_enabled)

        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok, self
        )
        self._agree_button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._agree_button.setText("동의")
        # Disabled until the checkbox is ticked — the button alone must not
        # be enough to grant consent.
        self._agree_button.setEnabled(False)
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(notice_label)
        layout.addWidget(self.consent_checkbox)
        layout.addWidget(self._buttons)

    def _update_agree_enabled(self, checked: bool) -> None:
        self._agree_button.setEnabled(checked)


# -- Search dialog (v0.5.1a, EXPERIMENTAL/ALPHA) ------------------------------

_SEARCH_RESULT_COLUMNS = ("제목", "크기", "시더", "출처")


def _format_optional_size(size_bytes: int | None) -> str:
    return format_size(size_bytes) if size_bytes is not None else "-"


def _format_optional_count(value: int | None) -> str:
    return str(value) if value is not None else "-"


class SearchDialog(QDialog):
    """EXPERIMENTAL/ALPHA search dialog (v0.5.1a, docs/ARCHITECTURE.md §9).

    Queries the injected :class:`SearchProvider` **directly** — not through
    :class:`~pytorrent_desktop.core.engine.TorrentEngine`, since search
    providers are a separate, optional subsystem (docs/SCOPE.md) — and
    catches :class:`~pytorrent_desktop.core.errors.SearchError` itself,
    showing an inline status message instead of propagating it. Only the
    final "다운로드 추가" step calls back out to :class:`MainWindow`, which
    remains the sole caller of ``TorrentEngine.add_magnet`` (the same
    division of responsibility every other dialog in this module follows).

    The legal notice banner at the top is **unconditional**: it is shown
    every time this dialog opens regardless of whether the one-time consent
    gate (:class:`SearchConsentDialog`) has already been accepted — the
    per-open banner and the one-time consent gate are deliberately separate
    requirements.

    Runs each query synchronously on the Qt main thread (blocking this modal
    dialog, not the rest of the app, for the HTTP round-trip) — acceptable
    for this experimental/alpha milestone; docs/ARCHITECTURE.md §9 sketches
    a worker-thread version as the eventual non-alpha design.
    """

    def __init__(
        self,
        provider: SearchProvider,
        *,
        timeout: float = 10.0,
        default_save_path: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"검색 (실험적/알파) — {provider.name}")
        self.setModal(True)
        self.resize(640, 420)
        self._provider = provider
        self._timeout = timeout
        self._default_save_path = default_save_path
        self._results: list[SearchResult] = []
        self._selected_magnet: str | None = None
        self._selected_save_path: str | None = None

        banner = QLabel(_SEARCH_LEGAL_NOTICE, self)
        banner.setWordWrap(True)
        banner.setProperty("role", "banner-warning")

        self.query_edit = QLineEdit(self)
        self.query_edit.setPlaceholderText("검색어 입력…")
        self.query_edit.returnPressed.connect(self._run_search)
        search_button = QPushButton("검색", self)
        search_button.setProperty("variant", "primary")
        search_button.clicked.connect(self._run_search)
        query_row = QHBoxLayout()
        query_row.addWidget(self.query_edit)
        query_row.addWidget(search_button)

        self.status_label = QLabel(self)
        self.status_label.setProperty("role", "hint")
        self.status_label.setVisible(False)

        self.results_table = QTableWidget(0, len(_SEARCH_RESULT_COLUMNS), self)
        self.results_table.setHorizontalHeaderLabels(list(_SEARCH_RESULT_COLUMNS))
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.results_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.results_table.horizontalHeader().setStretchLastSection(True)
        self.results_table.itemSelectionChanged.connect(self._update_download_enabled)

        self._download_button = QPushButton("다운로드 추가", self)
        self._download_button.setProperty("variant", "primary")
        self._download_button.setEnabled(False)
        self._download_button.clicked.connect(self._add_selected_to_downloads)

        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self._buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("닫기")
        self._buttons.rejected.connect(self.reject)
        self._buttons.addButton(self._download_button, QDialogButtonBox.ButtonRole.ActionRole)

        layout = QVBoxLayout(self)
        layout.addWidget(banner)
        layout.addLayout(query_row)
        layout.addWidget(self.status_label)
        layout.addWidget(self.results_table)
        layout.addWidget(self._buttons)

    # -- search --------------------------------------------------------------

    def _run_search(self) -> None:
        query = self.query_edit.text().strip()
        if not query:
            return
        self.results_table.setRowCount(0)
        self._results = []
        self._download_button.setEnabled(False)
        self._set_status("검색 중…")
        try:
            results = self._provider.search(query, timeout=self._timeout)
        except SearchError as exc:
            self._set_status(f"검색 오류: {exc}")
            return
        self._results = results
        if not results:
            self._set_status("검색 결과가 없습니다")
            return
        self._set_status(f"{len(results)}개 결과")
        self._populate_results(results)

    def _populate_results(self, results: list[SearchResult]) -> None:
        self.results_table.setRowCount(len(results))
        for row, result in enumerate(results):
            self.results_table.setItem(row, 0, QTableWidgetItem(result.title))
            self.results_table.setItem(
                row, 1, QTableWidgetItem(_format_optional_size(result.size_bytes))
            )
            self.results_table.setItem(
                row, 2, QTableWidgetItem(_format_optional_count(result.seeders))
            )
            self.results_table.setItem(row, 3, QTableWidgetItem(result.source))

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)
        self.status_label.setVisible(bool(text))

    # -- selection / download -------------------------------------------------

    def _update_download_enabled(self) -> None:
        self._download_button.setEnabled(bool(self.results_table.selectedItems()))

    def _add_selected_to_downloads(self) -> None:
        selected_rows = {index.row() for index in self.results_table.selectedIndexes()}
        if not selected_rows:
            return
        row = next(iter(selected_rows))
        if row >= len(self._results):
            return
        result = self._results[row]

        directory = QFileDialog.getExistingDirectory(
            self, "저장 경로 선택", self._default_save_path
        )
        if not directory:
            return  # cancelled the save-path picker; stay on the results view

        self._selected_magnet = result.magnet
        self._selected_save_path = directory
        self.accept()

    # -- result accessors (read after exec() returns Accepted) ---------------

    def selected_magnet(self) -> str | None:
        return self._selected_magnet

    def selected_save_path(self) -> str | None:
        return self._selected_save_path

    def results_count(self) -> int:
        """Test helper: how many results are currently loaded."""
        return len(self._results)
