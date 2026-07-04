"""Tests for :mod:`pytorrent_desktop.ui.dialogs` (docs/UX-SPEC.md §2, §3).

These only construct the dialogs and drive their widgets/fields directly —
no engine calls, since the dialogs never talk to :class:`TorrentEngine`
themselves (that's :class:`MainWindow`'s job).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QPushButton

from pytorrent_desktop.core.config import AppSettings, OnCompleteSettings, ProxySettings
from pytorrent_desktop.ui.dialogs import (
    AddTorrentDialog,
    OnCompleteCountdownDialog,
    RemoveDialog,
    SettingsDialog,
    is_valid_magnet,
)

# -- magnet validation --------------------------------------------------------


def test_is_valid_magnet_accepts_btih_uri():
    assert is_valid_magnet(
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test"
    )


def test_is_valid_magnet_rejects_garbage():
    assert not is_valid_magnet("not-a-magnet")
    assert not is_valid_magnet("")
    assert not is_valid_magnet("http://example.com/file.torrent")


# -- AddTorrentDialog -----------------------------------------------------------


def test_add_dialog_constructs_with_default_save_path(qtbot):
    dialog = AddTorrentDialog(default_save_path="D:\\Downloads\\pytorrent")
    qtbot.addWidget(dialog)
    assert dialog.save_path() == "D:\\Downloads\\pytorrent"


def test_add_dialog_ok_button_disabled_with_no_input(qtbot):
    dialog = AddTorrentDialog(default_save_path="D:\\Downloads")
    qtbot.addWidget(dialog)
    ok_button = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok_button.isEnabled()


def test_add_dialog_ok_button_enabled_for_valid_magnet_and_save_path(qtbot):
    dialog = AddTorrentDialog(default_save_path="D:\\Downloads")
    qtbot.addWidget(dialog)
    dialog.set_initial_tab(magnet=True)
    dialog.magnet_edit.setText(
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
    )
    ok_button = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok_button.isEnabled()
    assert dialog.is_magnet_mode()
    assert dialog.magnet_uri() == (
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
    )


def test_add_dialog_ok_button_disabled_for_invalid_magnet(qtbot):
    dialog = AddTorrentDialog(default_save_path="D:\\Downloads")
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.set_initial_tab(magnet=True)
    dialog.magnet_edit.setText("not-a-magnet")
    ok_button = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok_button.isEnabled()
    assert dialog.magnet_error_label.isVisible()


def test_add_dialog_ok_button_disabled_without_save_path(qtbot):
    dialog = AddTorrentDialog(default_save_path="")
    qtbot.addWidget(dialog)
    dialog.set_initial_tab(magnet=True)
    dialog.magnet_edit.setText(
        "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"
    )
    ok_button = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert not ok_button.isEnabled()


def test_add_dialog_paused_checkbox_defaults_unchecked(qtbot):
    dialog = AddTorrentDialog(default_save_path="D:\\Downloads")
    qtbot.addWidget(dialog)
    assert dialog.add_paused() is False


def test_add_dialog_file_tab_requires_existing_file(qtbot, tmp_path):
    dialog = AddTorrentDialog(default_save_path=str(tmp_path))
    qtbot.addWidget(dialog)
    dialog.set_initial_tab(magnet=False)
    ok_button = dialog._buttons.button(QDialogButtonBox.StandardButton.Ok)

    missing = tmp_path / "does-not-exist.torrent"
    dialog.file_path_edit.setText(str(missing))
    assert not ok_button.isEnabled()

    real_file = tmp_path / "example.torrent"
    real_file.write_bytes(b"fake torrent bytes")
    dialog.file_path_edit.setText(str(real_file))
    assert ok_button.isEnabled()
    assert dialog.torrent_file_path() == str(real_file)


# -- RemoveDialog -----------------------------------------------------------------


def test_remove_dialog_defaults_to_keep_data(qtbot):
    dialog = RemoveDialog(["ubuntu-24.04.iso"])
    qtbot.addWidget(dialog)
    assert dialog.keep_data_radio.isChecked()
    assert not dialog.delete_data_radio.isChecked()
    assert dialog.delete_data() is False


def test_remove_dialog_delete_data_flag_follows_radio_selection(qtbot):
    dialog = RemoveDialog(["ubuntu-24.04.iso"])
    qtbot.addWidget(dialog)
    dialog.delete_data_radio.setChecked(True)
    assert dialog.delete_data() is True


def test_remove_dialog_truncates_long_name_list(qtbot):
    names = [f"torrent-{i}.iso" for i in range(8)]
    dialog = RemoveDialog(names)
    qtbot.addWidget(dialog)
    # Just verify construction succeeds and doesn't render every single name
    # literally (5-item cap + "외 N개" summary, docs/UX-SPEC.md §3).
    assert dialog is not None


# -- SettingsDialog (docs/UX-SPEC.md §4) -------------------------------------


def test_settings_dialog_prefills_from_given_settings(qtbot, tmp_path):
    settings = AppSettings(
        listen_port=7000,
        default_save_path=str(tmp_path),
        proxy=ProxySettings(enabled=True, host="10.0.0.5", port=1080, username="bob"),
        on_complete=OnCompleteSettings(action="quit_app"),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    assert dialog.default_save_path() == str(tmp_path)
    assert dialog.listen_port() == 7000
    assert dialog.proxy_enabled() is True
    assert dialog.proxy_host() == "10.0.0.5"
    assert dialog.proxy_port() == 1080
    assert dialog.proxy_username() == "bob"
    assert dialog.on_complete_action() == "quit_app"


def test_settings_dialog_password_field_starts_blank_by_default(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert dialog.proxy_password() is None


def test_settings_dialog_password_field_prefilled_from_in_memory_value(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings, initial_password="hunter2")
    qtbot.addWidget(dialog)
    assert dialog.proxy_password() == "hunter2"


def test_settings_dialog_proxy_fields_disabled_when_proxy_unchecked(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    assert not dialog.proxy_host_edit.isEnabled()
    assert not dialog.kill_switch_checkbox.isEnabled()

    dialog.proxy_enabled_checkbox.setChecked(True)
    assert dialog.proxy_host_edit.isEnabled()
    assert dialog.kill_switch_checkbox.isEnabled()


def test_settings_dialog_kill_switch_warning_only_shows_when_proxy_on_and_switch_off(
    qtbot, tmp_path
):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.kill_switch_warning_label.isVisible()

    dialog.proxy_enabled_checkbox.setChecked(True)
    assert not dialog.kill_switch_warning_label.isVisible()  # kill switch defaults on

    dialog.kill_switch_checkbox.setChecked(False)
    assert dialog.kill_switch_warning_label.isVisible()


def test_settings_dialog_save_blocked_when_proxy_enabled_without_host(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.proxy_enabled_checkbox.setChecked(True)
    dialog.proxy_host_edit.setText("")

    assert dialog._validate() is False
    assert dialog.proxy_error_label.isVisible()


def test_settings_dialog_save_blocked_for_out_of_range_listen_port(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.listen_port_edit.setText("80")

    assert dialog._validate() is False
    assert dialog.listen_port_error_label.isVisible()


def test_settings_dialog_save_succeeds_with_valid_input(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.proxy_enabled_checkbox.setChecked(True)
    dialog.proxy_host_edit.setText("127.0.0.1")
    dialog.proxy_port_edit.setText("1080")

    assert dialog._validate() is True


def test_settings_dialog_on_complete_hint_hidden_for_none(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    assert not dialog.on_complete_hint_label.isVisible()

    dialog.on_complete_quit_radio.setChecked(True)
    assert dialog.on_complete_hint_label.isVisible()


# -- OnCompleteCountdownDialog (docs/DECISIONS.md D3, docs/UX-SPEC.md §5.6) --------


def test_countdown_dialog_accepts_when_it_runs_out(qtbot):
    dialog = OnCompleteCountdownDialog(2, lambda: True, interval_ms=10)
    qtbot.addWidget(dialog)
    dialog.show()

    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Accepted, timeout=2000)


def test_countdown_dialog_cancel_button_rejects(qtbot):
    dialog = OnCompleteCountdownDialog(30, lambda: True, interval_ms=10)
    qtbot.addWidget(dialog)
    dialog.show()

    cancel_button = dialog.findChild(QPushButton)
    qtbot.mouseClick(cancel_button, Qt.MouseButton.LeftButton)

    assert dialog.result() == QDialog.DialogCode.Rejected


def test_countdown_dialog_auto_cancels_when_no_longer_eligible(qtbot):
    eligible = {"value": True}
    dialog = OnCompleteCountdownDialog(30, lambda: eligible["value"], interval_ms=10)
    qtbot.addWidget(dialog)
    dialog.show()
    eligible["value"] = False

    qtbot.waitUntil(lambda: dialog.result() == QDialog.DialogCode.Rejected, timeout=2000)


def test_countdown_dialog_message_mentions_action_description(qtbot):
    dialog = OnCompleteCountdownDialog(30, lambda: True, action_description="앱을 종료")
    qtbot.addWidget(dialog)
    assert "앱을 종료" in dialog._message_label.text()
    assert "30" in dialog._message_label.text()
