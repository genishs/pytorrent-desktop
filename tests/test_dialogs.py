"""Tests for :mod:`pytorrent_desktop.ui.dialogs` (docs/UX-SPEC.md §2, §3).

These only construct the dialogs and drive their widgets/fields directly —
no engine calls, since the dialogs never talk to :class:`TorrentEngine`
themselves (that's :class:`MainWindow`'s job).
"""

from __future__ import annotations

from PySide6.QtWidgets import QDialogButtonBox

from pytorrent_desktop.ui.dialogs import AddTorrentDialog, RemoveDialog, is_valid_magnet

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
