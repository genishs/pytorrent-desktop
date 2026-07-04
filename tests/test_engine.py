"""Minimal headless smoke tests for :class:`TorrentEngine`.

These only verify the engine can be constructed and torn down against a real
libtorrent session, and that its status/description surface has the expected
shape. They intentionally do not add/download any torrent (no network access
in CI). The developer is expected to expand coverage as features land.
"""

from __future__ import annotations

from pytorrent_desktop.core.engine import TorrentEngine


def test_engine_can_be_created_and_shutdown() -> None:
    engine = TorrentEngine()
    try:
        assert engine is not None
    finally:
        engine.shutdown()


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
