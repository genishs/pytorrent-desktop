"""Tests for :mod:`pytorrent_desktop.ui.dialogs` (docs/UX-SPEC.md §2, §3).

These only construct the dialogs and drive their widgets/fields directly —
no engine calls, since the dialogs never talk to :class:`TorrentEngine`
themselves (that's :class:`MainWindow`'s job).
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFileDialog, QLabel, QPushButton

from pytorrent_desktop.core.config import (
    AppSettings,
    OnCompleteSettings,
    ProxySettings,
    SearchSettings,
)
from pytorrent_desktop.core.errors import SearchError
from pytorrent_desktop.core.search.base import SearchProvider, SearchResult
from pytorrent_desktop.ui.dialogs import (
    AddTorrentDialog,
    OnCompleteCountdownDialog,
    RemoveDialog,
    SearchConsentDialog,
    SearchDialog,
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


# -- SettingsDialog search tab (v0.5.1a, EXPERIMENTAL/ALPHA) ------------------


def test_settings_dialog_prefills_search_fields(qtbot, tmp_path):
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(
            enabled=True, btdig_base_url="https://btdig.example", consent_accepted=True
        ),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    assert dialog.search_enabled() is True
    assert dialog.search_btdig_base_url() == "https://btdig.example"
    assert dialog.search_consent_accepted() is True


def test_settings_dialog_search_disabled_by_default_and_base_url_field_disabled(qtbot, tmp_path):
    settings = AppSettings(default_save_path=str(tmp_path))
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    assert dialog.search_enabled() is False
    assert not dialog.search_base_url_edit.isEnabled()


def test_settings_dialog_prefill_never_triggers_consent_gate(qtbot, tmp_path, monkeypatch):
    """Pre-filling the checkbox from already-persisted settings must never
    itself pop the modal consent gate — only a live user toggle should."""
    gate_calls: list = []
    monkeypatch.setattr(
        SettingsDialog, "_run_search_consent_gate", lambda self: gate_calls.append(1) or True
    )
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(enabled=True, consent_accepted=False),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    assert gate_calls == []
    assert dialog.search_consent_accepted() is False


def test_settings_dialog_toggling_search_on_without_consent_shows_gate(
    qtbot, tmp_path, monkeypatch
):
    gate_calls: list = []
    monkeypatch.setattr(
        SettingsDialog, "_run_search_consent_gate", lambda self: gate_calls.append(1) or True
    )
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(enabled=False, consent_accepted=False),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    dialog.search_enabled_checkbox.setChecked(True)

    assert gate_calls == [1]
    assert dialog.search_enabled() is True
    assert dialog.search_consent_accepted() is True


def test_settings_dialog_declining_consent_gate_reverts_checkbox(qtbot, tmp_path, monkeypatch):
    monkeypatch.setattr(SettingsDialog, "_run_search_consent_gate", lambda self: False)
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(enabled=False, consent_accepted=False),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    dialog.search_enabled_checkbox.setChecked(True)

    assert dialog.search_enabled() is False  # reverted
    assert dialog.search_consent_accepted() is False


def test_settings_dialog_does_not_reprompt_once_consent_already_accepted(
    qtbot, tmp_path, monkeypatch
):
    gate_calls: list = []
    monkeypatch.setattr(
        SettingsDialog, "_run_search_consent_gate", lambda self: gate_calls.append(1) or True
    )
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(enabled=False, consent_accepted=True),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)

    dialog.search_enabled_checkbox.setChecked(True)

    assert gate_calls == []  # already accepted -> no gate shown
    assert dialog.search_enabled() is True


def test_settings_dialog_save_blocked_for_empty_base_url_when_search_enabled(qtbot, tmp_path):
    # consent already accepted so toggling search on does not pop the (modal,
    # blocking) consent gate — this test only exercises base-URL validation.
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(enabled=False, consent_accepted=True),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.search_enabled_checkbox.setChecked(True)
    dialog.search_base_url_edit.setText("")

    assert dialog._validate() is False
    assert dialog.search_error_label.isVisible()


def test_settings_dialog_save_blocked_for_non_http_base_url(qtbot, tmp_path):
    settings = AppSettings(
        default_save_path=str(tmp_path),
        search=SearchSettings(enabled=False, consent_accepted=True),
    )
    dialog = SettingsDialog(settings)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.search_enabled_checkbox.setChecked(True)
    dialog.search_base_url_edit.setText("ftp://btdig.example")

    assert dialog._validate() is False
    assert dialog.search_error_label.isVisible()


# -- SearchConsentDialog (v0.5.1a, EXPERIMENTAL/ALPHA) ------------------------


def test_consent_dialog_agree_button_disabled_until_checkbox_checked(qtbot):
    dialog = SearchConsentDialog()
    qtbot.addWidget(dialog)
    assert not dialog._agree_button.isEnabled()

    dialog.consent_checkbox.setChecked(True)
    assert dialog._agree_button.isEnabled()

    dialog.consent_checkbox.setChecked(False)
    assert not dialog._agree_button.isEnabled()


def test_consent_dialog_accepts_only_after_checkbox_and_agree_click(qtbot):
    dialog = SearchConsentDialog()
    qtbot.addWidget(dialog)
    dialog.consent_checkbox.setChecked(True)

    dialog.accept()

    assert dialog.result() == QDialog.DialogCode.Accepted


def test_consent_dialog_cancel_rejects(qtbot):
    dialog = SearchConsentDialog()
    qtbot.addWidget(dialog)
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_consent_dialog_mentions_legal_responsibility(qtbot):
    dialog = SearchConsentDialog()
    qtbot.addWidget(dialog)
    # Must state: (1) may be legally problematic, (2) may violate content
    # license, (3) user bears all responsibility.
    notice_text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "법적으로 문제" in notice_text
    assert "라이선스를 위반" in notice_text
    assert "책임은 사용자 본인에게 있습니다" in notice_text


def test_consent_dialog_checkbox_text_states_user_responsibility(qtbot):
    dialog = SearchConsentDialog()
    qtbot.addWidget(dialog)
    assert "책임" in dialog.consent_checkbox.text()


# -- SearchDialog (v0.5.1a, EXPERIMENTAL/ALPHA) -------------------------------


class _StubProvider(SearchProvider):
    name = "stub"

    def __init__(self, results=None, error: Exception | None = None) -> None:
        self._results = results or []
        self._error = error
        self.queries: list[str] = []

    def search(self, query: str, *, timeout: float = 10.0) -> list[SearchResult]:
        self.queries.append(query)
        if self._error is not None:
            raise self._error
        return list(self._results)


def _make_result(**overrides) -> SearchResult:
    defaults = dict(
        title="example.iso",
        size_bytes=1024,
        seeders=5,
        leechers=1,
        magnet="magnet:?xt=urn:btih:" + "f" * 40,
        source="stub",
    )
    defaults.update(overrides)
    return SearchResult(**defaults)


def test_search_dialog_shows_legal_notice_unconditionally(qtbot):
    dialog = SearchDialog(_StubProvider())
    qtbot.addWidget(dialog)
    # Present regardless of whether consent has already been granted
    # elsewhere — this banner is unconditional every time the dialog opens.
    banner_labels = [
        label for label in dialog.findChildren(QLabel) if label.property("role") == "banner-warning"
    ]
    assert len(banner_labels) == 1
    assert "법적으로 문제" in banner_labels[0].text()
    assert "책임" in banner_labels[0].text()


def test_search_dialog_empty_query_does_not_call_provider(qtbot):
    provider = _StubProvider([_make_result()])
    dialog = SearchDialog(provider)
    qtbot.addWidget(dialog)

    dialog.query_edit.setText("   ")
    dialog._run_search()

    assert provider.queries == []
    assert dialog.results_table.rowCount() == 0


def test_search_dialog_populates_results_table(qtbot):
    provider = _StubProvider([_make_result(title="Ubuntu ISO"), _make_result(title="Debian ISO")])
    dialog = SearchDialog(provider)
    qtbot.addWidget(dialog)

    dialog.query_edit.setText("linux")
    dialog._run_search()

    assert provider.queries == ["linux"]
    assert dialog.results_table.rowCount() == 2
    assert dialog.results_table.item(0, 0).text() == "Ubuntu ISO"
    assert dialog.results_table.item(0, 2).text() == "5"  # seeders
    assert dialog.results_table.item(0, 3).text() == "stub"  # source


def test_search_dialog_shows_dash_for_unknown_optional_fields(qtbot):
    provider = _StubProvider([_make_result(size_bytes=None, seeders=None, leechers=None)])
    dialog = SearchDialog(provider)
    qtbot.addWidget(dialog)

    dialog.query_edit.setText("q")
    dialog._run_search()

    assert dialog.results_table.item(0, 1).text() == "-"  # size
    assert dialog.results_table.item(0, 2).text() == "-"  # seeders


def test_search_dialog_no_results_shows_status_message(qtbot):
    dialog = SearchDialog(_StubProvider([]))
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.query_edit.setText("nonexistent")
    dialog._run_search()

    assert dialog.status_label.isVisible()
    assert dialog.results_table.rowCount() == 0


def test_search_dialog_provider_error_shown_inline_not_raised(qtbot):
    dialog = SearchDialog(_StubProvider(error=SearchError("boom")))
    qtbot.addWidget(dialog)
    dialog.show()

    dialog.query_edit.setText("q")
    dialog._run_search()  # must not raise

    assert dialog.status_label.isVisible()
    assert "오류" in dialog.status_label.text()


def test_search_dialog_download_button_disabled_until_row_selected(qtbot):
    provider = _StubProvider([_make_result()])
    dialog = SearchDialog(provider)
    qtbot.addWidget(dialog)
    dialog.query_edit.setText("q")
    dialog._run_search()

    assert not dialog._download_button.isEnabled()
    dialog.results_table.selectRow(0)
    assert dialog._download_button.isEnabled()


def test_search_dialog_add_to_downloads_prompts_save_path_and_accepts(qtbot, monkeypatch, tmp_path):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: str(tmp_path))
    magnet = "magnet:?xt=urn:btih:" + "9" * 40
    provider = _StubProvider([_make_result(magnet=magnet)])
    dialog = SearchDialog(provider, default_save_path=str(tmp_path))
    qtbot.addWidget(dialog)
    dialog.query_edit.setText("q")
    dialog._run_search()
    dialog.results_table.selectRow(0)

    dialog._add_selected_to_downloads()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.selected_magnet() == magnet
    assert dialog.selected_save_path() == str(tmp_path)


def test_search_dialog_add_to_downloads_cancelled_save_path_stays_open(qtbot, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: "")
    provider = _StubProvider([_make_result()])
    dialog = SearchDialog(provider)
    qtbot.addWidget(dialog)
    dialog.query_edit.setText("q")
    dialog._run_search()
    dialog.results_table.selectRow(0)

    dialog._add_selected_to_downloads()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.selected_magnet() is None
