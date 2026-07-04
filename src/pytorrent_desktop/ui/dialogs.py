"""Add-torrent and remove-confirmation dialogs (docs/UX-SPEC.md §2, §3).

Both dialogs only collect input; they never call into
:class:`~pytorrent_desktop.core.engine.TorrentEngine` themselves — that stays
in :class:`~pytorrent_desktop.ui.main_window.MainWindow`, which is the only
place engine errors are caught and turned into user-facing messages.
"""

from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

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
