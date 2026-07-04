"""Headless, network-free tests for :class:`TorrentEngine`.

These verify the engine can be constructed and torn down against a real
libtorrent session, that its status/description surface has the expected
(extended, D4) shape, and that the typed error hierarchy fires for the input
validation the engine is responsible for. They intentionally never let a
torrent actually download (no network access in CI) — ``add_magnet`` only
needs to create a handle; libtorrent making a handle does not require any
peer/tracker traffic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pytorrent_desktop.core.engine import EngineConfig, ProxyConfig, TorrentEngine
from pytorrent_desktop.core.errors import (
    DuplicateTorrentError,
    InvalidMagnetError,
    SavePathError,
    TorrentFileError,
    UnknownTorrentError,
)

# A syntactically valid magnet URI (well-formed 40-hex v1 info-hash). Adding
# it only creates a handle; it never contacts a tracker/peer within these
# tests.
VALID_MAGNET = "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=test-torrent"


def test_engine_can_be_created_and_shutdown() -> None:
    engine = TorrentEngine()
    try:
        assert engine is not None
    finally:
        engine.shutdown()


def test_shutdown_is_idempotent() -> None:
    engine = TorrentEngine()
    engine.shutdown()
    engine.shutdown()  # must not raise


def test_snapshot_returns_list() -> None:
    engine = TorrentEngine()
    try:
        snapshot = engine.snapshot()
        assert isinstance(snapshot, list)
        assert snapshot == []
    finally:
        engine.shutdown()


def test_describe_mentions_libtorrent() -> None:
    engine = TorrentEngine()
    try:
        assert "libtorrent" in engine.describe()
    finally:
        engine.shutdown()


def test_engine_accepts_custom_config(tmp_path: Path) -> None:
    config = EngineConfig(listen_port=0, data_dir=tmp_path, enable_dht=False)
    engine = TorrentEngine(config)
    try:
        assert "libtorrent" in engine.describe()
    finally:
        engine.shutdown()


def test_proxy_config_is_a_plain_dataclass() -> None:
    cfg = ProxyConfig(host="127.0.0.1", port=1080)
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 1080
    assert cfg.kill_switch is True


def test_add_magnet_creates_handle_without_downloading(tmp_path: Path) -> None:
    engine = TorrentEngine()
    try:
        info_hash = engine.add_magnet(VALID_MAGNET, tmp_path)
        assert isinstance(info_hash, str)
        assert len(info_hash) == 40

        snapshot = engine.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0].info_hash == info_hash
    finally:
        engine.shutdown()


def test_add_magnet_duplicate_raises_duplicate_torrent_error(tmp_path: Path) -> None:
    engine = TorrentEngine()
    try:
        engine.add_magnet(VALID_MAGNET, tmp_path)
        with pytest.raises(DuplicateTorrentError):
            engine.add_magnet(VALID_MAGNET, tmp_path)
        # still only one handle registered
        assert len(engine.snapshot()) == 1
    finally:
        engine.shutdown()


def test_add_magnet_invalid_uri_raises_invalid_magnet_error(tmp_path: Path) -> None:
    engine = TorrentEngine()
    try:
        with pytest.raises(InvalidMagnetError):
            engine.add_magnet("not-a-magnet", tmp_path)
    finally:
        engine.shutdown()


def test_add_magnet_bad_save_path_raises_save_path_error(tmp_path: Path) -> None:
    engine = TorrentEngine()
    try:
        with pytest.raises(SavePathError):
            engine.add_magnet(VALID_MAGNET, tmp_path / "does-not-exist")
    finally:
        engine.shutdown()


def test_add_torrent_file_missing_file_raises_torrent_file_error(tmp_path: Path) -> None:
    engine = TorrentEngine()
    try:
        with pytest.raises(TorrentFileError):
            engine.add_torrent_file(tmp_path / "missing.torrent", tmp_path)
    finally:
        engine.shutdown()


def test_pause_unknown_torrent_raises_unknown_torrent_error() -> None:
    engine = TorrentEngine()
    try:
        with pytest.raises(UnknownTorrentError):
            engine.pause("0" * 40)
    finally:
        engine.shutdown()


def test_remove_unknown_torrent_raises_unknown_torrent_error() -> None:
    engine = TorrentEngine()
    try:
        with pytest.raises(UnknownTorrentError):
            engine.remove("0" * 40)
    finally:
        engine.shutdown()


def test_snapshot_status_has_extended_fields(tmp_path: Path) -> None:
    engine = TorrentEngine()
    try:
        engine.add_magnet(VALID_MAGNET, tmp_path)
        status = engine.snapshot()[0]

        assert status.name
        assert status.save_path
        assert isinstance(status.total_bytes, int)
        assert isinstance(status.downloaded_bytes, int)
        assert 0.0 <= status.progress <= 1.0
        assert isinstance(status.download_rate, int)
        assert isinstance(status.upload_rate, int)
        assert isinstance(status.num_peers, int)
        assert isinstance(status.num_seeds, int)
        assert isinstance(status.state, str)
        assert isinstance(status.is_paused, bool)
        assert isinstance(status.is_finished, bool)
        assert isinstance(status.queue_position, int)
        assert status.error is None
    finally:
        engine.shutdown()
