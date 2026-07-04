"""Tests for :class:`pytorrent_desktop.core.resume_store.ResumeStore`.

Covers the data-safety properties docs/ARCHITECTURE.md §5 calls out: atomic
writes (§5.2), quarantining unparseable files instead of deleting them
(§5.3), and a real bencoded-resume-blob round trip through
``lt.write_resume_data_buf`` / ``lt.read_resume_data`` (not a hand-rolled
fake buffer — this is the exact opaque blob shape the engine hands the
store).
"""

from __future__ import annotations

import time
from pathlib import Path

import libtorrent as lt
import pytest

from pytorrent_desktop.core.config import AppPaths
from pytorrent_desktop.core.resume_store import ResumeStore

_MAGNET = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test-torrent"


def _real_resume_buf(save_path: Path) -> bytes:
    """Produce a genuine bencoded resume blob via a real (offline) session.

    Mirrors what ``TorrentEngine`` does: add a torrent, request
    ``save_resume_data``, drain the resulting alert, and encode it with
    ``lt.write_resume_data_buf`` — the exact function the engine uses.
    """
    session = lt.session({"listen_interfaces": "0.0.0.0:0", "enable_dht": False})
    try:
        params = lt.parse_magnet_uri(_MAGNET)
        params.save_path = str(save_path)
        params.flags |= lt.torrent_flags.auto_managed
        handle = session.add_torrent(params)
        handle.save_resume_data(
            lt.torrent_handle.save_info_dict | lt.torrent_handle.flush_disk_cache
        )
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            session.wait_for_alert(200)
            for alert in session.pop_alerts():
                if isinstance(alert, lt.save_resume_data_alert):
                    return lt.write_resume_data_buf(alert.params)
                if isinstance(alert, lt.save_resume_data_failed_alert):
                    pytest.fail(f"resume save failed in test fixture: {alert.error.message()}")
        pytest.fail("no save_resume_data_alert within timeout")
    finally:
        del session


def test_save_then_load_all_round_trips_a_real_resume_blob(tmp_path: Path) -> None:
    save_dir = tmp_path / "save"
    save_dir.mkdir()
    buf = _real_resume_buf(save_dir)

    store = ResumeStore(AppPaths(tmp_path / "appdata"))
    key = "0123456789abcdef0123456789abcdef01234567"
    store.save(key, buf)

    loaded = store.load_all()
    assert len(loaded) == 1
    atp = loaded[0]
    assert atp.save_path == str(save_dir)


def test_save_is_atomic_and_leaves_no_tmp_file(tmp_path: Path) -> None:
    store = ResumeStore(AppPaths(tmp_path / "appdata"))
    key = "a" * 40
    store.save(key, b"first-write")
    store.save(key, b"second-write")  # overwrite

    target = store.path_for(key)
    assert target.read_bytes() == b"second-write"
    assert not target.with_suffix(target.suffix + ".tmp").exists()


def test_corrupt_resume_file_is_quarantined_not_deleted(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path / "appdata")
    store = ResumeStore(paths)
    bad_file = paths.resume_dir / "deadbeef.fastresume"
    bad_file.write_bytes(b"this is not a valid bencoded resume blob")

    loaded = store.load_all()

    assert loaded == []  # corrupt entry skipped, does not raise
    assert not bad_file.exists()  # moved out of resume_dir...
    quarantined = list(paths.resume_quarantine_dir.glob("*.fastresume"))
    assert len(quarantined) == 1  # ...and preserved in bad/ rather than deleted


def test_load_all_with_no_resume_files_returns_empty_list(tmp_path: Path) -> None:
    store = ResumeStore(AppPaths(tmp_path / "appdata"))
    assert store.load_all() == []


def test_delete_removes_the_resume_file(tmp_path: Path) -> None:
    store = ResumeStore(AppPaths(tmp_path / "appdata"))
    key = "b" * 40
    store.save(key, b"data")
    assert store.path_for(key).exists()

    store.delete(key)

    assert not store.path_for(key).exists()


def test_delete_is_idempotent_for_a_missing_key(tmp_path: Path) -> None:
    store = ResumeStore(AppPaths(tmp_path / "appdata"))
    store.delete("c" * 40)  # must not raise even though nothing was ever saved


def test_app_paths_ensure_creates_resume_and_quarantine_dirs(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path / "appdata")
    assert not paths.resume_dir.exists()

    ResumeStore(paths)  # construction calls AppPaths.ensure()

    assert paths.resume_dir.is_dir()
    assert paths.resume_quarantine_dir.is_dir()
