"""Headless, network-free tests for :class:`TorrentEngine`.

These verify the engine can be constructed and torn down against a real
libtorrent session, that its status/description surface has the expected
(extended, D4) shape, and that the typed error hierarchy fires for the input
validation the engine is responsible for. They intentionally never let a
torrent actually download (no network access in CI) — ``add_magnet`` only
needs to create a handle; libtorrent making a handle does not require any
peer/tracker traffic.

Every engine is built with ``EngineConfig(data_dir=tmp_path)`` (v0.3.0+):
the engine now persists resume data under ``data_dir/resume`` and, without an
explicit override, ``EngineConfig.data_dir`` defaults to the *real*
``%APPDATA%\\pytorrent-desktop`` (docs/ARCHITECTURE.md §7) — tests must not
write there.
"""

from __future__ import annotations

import time
from pathlib import Path

import libtorrent as lt
import pytest

from pytorrent_desktop.core.engine import EngineConfig, ProxyConfig, TorrentEngine
from pytorrent_desktop.core.errors import (
    DuplicateTorrentError,
    InvalidMagnetError,
    ProxyConfigError,
    SavePathError,
    TorrentFileError,
    UnknownTorrentError,
)

# A syntactically valid, well-formed 40-hex v1 info-hash. Adding it only
# creates a handle; it never contacts a tracker/peer within these tests.
_BASE_HASH = "0123456789abcdef0123456789abcdef01234567"
VALID_MAGNET = f"magnet:?xt=urn:btih:{_BASE_HASH}&dn=test-torrent"


def _engine(tmp_path: Path, **overrides) -> TorrentEngine:
    """Build a TorrentEngine with an isolated, tmp_path-rooted data_dir."""
    config = EngineConfig(data_dir=tmp_path / "appdata", **overrides)
    return TorrentEngine(config)


def test_engine_can_be_created_and_shutdown(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        assert engine is not None
    finally:
        engine.shutdown()


def test_shutdown_is_idempotent(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.shutdown()
    engine.shutdown()  # must not raise


def test_snapshot_returns_list(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        snapshot = engine.snapshot()
        assert isinstance(snapshot, list)
        assert snapshot == []
    finally:
        engine.shutdown()


def test_describe_mentions_libtorrent(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
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
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hash = engine.add_magnet(VALID_MAGNET, save_dir)
        assert isinstance(info_hash, str)
        assert len(info_hash) == 40

        snapshot = engine.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0].info_hash == info_hash
    finally:
        engine.shutdown()


def test_add_magnet_duplicate_raises_duplicate_torrent_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        engine.add_magnet(VALID_MAGNET, save_dir)
        with pytest.raises(DuplicateTorrentError):
            engine.add_magnet(VALID_MAGNET, save_dir)
        # still only one handle registered
        assert len(engine.snapshot()) == 1
    finally:
        engine.shutdown()


def test_add_magnet_invalid_uri_raises_invalid_magnet_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        with pytest.raises(InvalidMagnetError):
            engine.add_magnet("not-a-magnet", save_dir)
    finally:
        engine.shutdown()


def test_add_magnet_bad_save_path_raises_save_path_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(SavePathError):
            engine.add_magnet(VALID_MAGNET, tmp_path / "does-not-exist")
    finally:
        engine.shutdown()


def test_add_torrent_file_missing_file_raises_torrent_file_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        with pytest.raises(TorrentFileError):
            engine.add_torrent_file(tmp_path / "missing.torrent", save_dir)
    finally:
        engine.shutdown()


def test_pause_unknown_torrent_raises_unknown_torrent_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(UnknownTorrentError):
            engine.pause("0" * 40)
    finally:
        engine.shutdown()


def test_remove_unknown_torrent_raises_unknown_torrent_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(UnknownTorrentError):
            engine.remove("0" * 40)
    finally:
        engine.shutdown()


def test_snapshot_status_has_extended_fields(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        engine.add_magnet(VALID_MAGNET, save_dir)
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


# -- resume-data persistence (v0.3.0, §4.3/§5) ---------------------------


def test_add_magnet_writes_a_resume_file_after_a_poll_tick(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hash = engine.add_magnet(VALID_MAGNET, save_dir)
        # add_magnet only *requests* the save (§5.1 item 1); snapshot()'s
        # alert pump is what actually collects and writes it.
        resume_file = tmp_path / "appdata" / "resume" / f"{info_hash}.fastresume"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not resume_file.exists():
            engine.snapshot()
        assert resume_file.exists()
    finally:
        engine.shutdown()


def test_remove_deletes_the_resume_file(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hash = engine.add_magnet(VALID_MAGNET, save_dir)
        resume_file = tmp_path / "appdata" / "resume" / f"{info_hash}.fastresume"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not resume_file.exists():
            engine.snapshot()
        assert resume_file.exists()

        engine.remove(info_hash)

        assert not resume_file.exists()
    finally:
        engine.shutdown()


def test_torrents_are_restored_from_resume_data_on_next_engine_startup(tmp_path: Path) -> None:
    data_dir = tmp_path / "appdata"
    save_dir = tmp_path / "save"
    save_dir.mkdir()

    engine = TorrentEngine(EngineConfig(data_dir=data_dir))
    try:
        info_hash = engine.add_magnet(VALID_MAGNET, save_dir)
        resume_file = data_dir / "resume" / f"{info_hash}.fastresume"
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not resume_file.exists():
            engine.snapshot()
        assert resume_file.exists()
    finally:
        engine.shutdown()  # shutdown's own flush must not remove the file

    # Fresh engine, same data_dir: the torrent must come back automatically
    # (docs/ARCHITECTURE.md §5.3) — no add_magnet/add_torrent_file call.
    engine2 = TorrentEngine(EngineConfig(data_dir=data_dir))
    try:
        snapshot = engine2.snapshot()
        assert len(snapshot) == 1
        assert snapshot[0].info_hash == info_hash
    finally:
        engine2.shutdown()


def test_corrupt_resume_file_does_not_block_startup(tmp_path: Path) -> None:
    data_dir = tmp_path / "appdata"
    (data_dir / "resume").mkdir(parents=True)
    (data_dir / "resume" / "garbage.fastresume").write_bytes(b"not bencoded data")

    engine = TorrentEngine(EngineConfig(data_dir=data_dir))
    try:
        assert engine.snapshot() == []  # corrupt entry skipped, startup didn't raise
        assert (data_dir / "resume" / "bad" / "garbage.fastresume").exists()
    finally:
        engine.shutdown()


# -- sequential queue (v0.3.0, §6) ----------------------------------------


def _add_n_magnets(engine: TorrentEngine, save_dir: Path, n: int) -> list[str]:
    """Add ``n`` torrents with distinct, well-formed info-hashes (no network)."""
    hashes = []
    for i in range(n):
        magnet = f"magnet:?xt=urn:btih:{i}{_BASE_HASH[1:]}"
        hashes.append(engine.add_magnet(magnet, save_dir))
    return hashes


def test_new_torrents_get_sequential_queue_positions(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hashes = _add_n_magnets(engine, save_dir, 3)
        by_hash = {s.info_hash: s.queue_position for s in engine.snapshot()}
        assert [by_hash[h] for h in info_hashes] == [0, 1, 2]
    finally:
        engine.shutdown()


def test_move_in_queue_top_reorders(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hashes = _add_n_magnets(engine, save_dir, 3)
        engine.move_in_queue(info_hashes[2], "top")
        by_hash = {s.info_hash: s.queue_position for s in engine.snapshot()}
        assert by_hash[info_hashes[2]] == 0
        assert by_hash[info_hashes[0]] == 1
        assert by_hash[info_hashes[1]] == 2
    finally:
        engine.shutdown()


def test_move_in_queue_up_and_down(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hashes = _add_n_magnets(engine, save_dir, 2)

        engine.move_in_queue(info_hashes[1], "up")
        by_hash = {s.info_hash: s.queue_position for s in engine.snapshot()}
        assert by_hash[info_hashes[1]] == 0
        assert by_hash[info_hashes[0]] == 1

        engine.move_in_queue(info_hashes[1], "down")
        by_hash = {s.info_hash: s.queue_position for s in engine.snapshot()}
        assert by_hash[info_hashes[1]] == 1
        assert by_hash[info_hashes[0]] == 0
    finally:
        engine.shutdown()


def test_move_in_queue_unknown_torrent_raises_unknown_torrent_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(UnknownTorrentError):
            engine.move_in_queue("0" * 40, "up")
    finally:
        engine.shutdown()


def test_set_sequential_queue_toggles_active_downloads_setting(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        engine.set_sequential_queue(True)
        assert engine._session.get_settings()["active_downloads"] == 1

        engine.set_sequential_queue(False)
        assert engine._session.get_settings()["active_downloads"] == -1
    finally:
        engine.shutdown()


def test_key_from_hashes_matches_the_magnet_info_hash() -> None:
    params = lt.parse_magnet_uri(VALID_MAGNET)
    key = TorrentEngine._key_from_hashes(params.info_hashes)
    assert key == _BASE_HASH


# -- shutdown resume-data flush (v0.3.0, §4.3) ----------------------------


class _FakeAlertSession:
    """Stand-in for ``lt.session`` inside ``_blocking_flush``'s drain loop.

    ``lt.save_resume_data_alert``/``lt.save_resume_data_failed_alert`` can't
    be constructed from Python (native-only types), so the "classify one
    alert" step is monkeypatched separately (see ``fake_process`` in the
    tests below) and this fake session just replays canned batches of opaque
    sentinel objects through the same ``wait_for_alert``/``pop_alerts`` shape
    the real session exposes.
    """

    def __init__(self, batches: list[list[object]]) -> None:
        self._batches = iter(batches)

    def wait_for_alert(self, timeout_ms: int) -> None:
        return None

    def pop_alerts(self) -> list[object]:
        return next(self._batches, [])


def test_blocking_flush_decrements_outstanding_on_failed_alert_too(tmp_path: Path) -> None:
    """Regression test for the documented hang bug (§4.3): a drain loop that
    only decrements ``outstanding`` on success — and not on
    ``save_resume_data_failed_alert`` — blocks to the full timeout whenever a
    torrent's resume save fails (e.g. a magnet that never got metadata).
    """
    engine = _engine(tmp_path)
    real_session = engine._session
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hashes = _add_n_magnets(engine, save_dir, 2)
        handles = [engine._get_handle(h) for h in info_hashes]

        sentinel_saved = object()
        sentinel_failed = object()

        def fake_process(alert: object) -> str | None:
            if alert is sentinel_saved:
                return "saved"
            if alert is sentinel_failed:
                return "failed"
            return None

        engine._process_resume_alert = fake_process  # type: ignore[method-assign]
        # One batch containing one "success" and one "failure" sentinel:
        # both must retire "outstanding" so the loop exits immediately
        # instead of blocking to the timeout.
        engine._session = _FakeAlertSession([[sentinel_saved, sentinel_failed]])

        start = time.monotonic()
        saved_count = engine._blocking_flush(handles, timeout_s=5.0)
        elapsed = time.monotonic() - start

        assert saved_count == 1
        assert elapsed < 1.0  # must not have blocked anywhere near the 5s timeout
    finally:
        engine._session = real_session
        engine.shutdown()


# -- privacy / kill switch (v0.4.0, §11, docs/DECISIONS.md D1) ---------------


def test_configure_privacy_applies_the_documented_no_leak_settings(tmp_path: Path) -> None:
    """§11.1/§11.2: anonymous_mode + proxy_hostnames is the load-bearing
    guarantee, kill_switch=True must also turn off DHT/LSD/UPnP/NAT-PMP."""
    engine = _engine(tmp_path)
    try:
        engine.configure_privacy(
            ProxyConfig(host="127.0.0.1", port=1080, username="alice", password="secret")
        )
        settings = engine._session.get_settings()
        assert settings["proxy_type"] == int(lt.proxy_type_t.socks5_pw)
        assert settings["proxy_hostname"] == "127.0.0.1"
        assert settings["proxy_port"] == 1080
        assert settings["proxy_username"] == "alice"
        assert settings["proxy_password"] == "secret"
        assert settings["proxy_hostnames"] is True
        assert settings["proxy_peer_connections"] is True
        assert settings["proxy_tracker_connections"] is True
        assert settings["anonymous_mode"] is True
        assert settings["enable_dht"] is False
        assert settings["enable_lsd"] is False
        assert settings["enable_upnp"] is False
        assert settings["enable_natpmp"] is False
        assert engine.privacy_status() == "enabled"
    finally:
        engine.shutdown()


def test_configure_privacy_without_username_uses_plain_socks5(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        engine.configure_privacy(ProxyConfig(host="10.0.0.1", port=9050))
        settings = engine._session.get_settings()
        assert settings["proxy_type"] == int(lt.proxy_type_t.socks5)
    finally:
        engine.shutdown()


def test_configure_privacy_kill_switch_off_leaves_side_channels_enabled(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        engine.configure_privacy(ProxyConfig(host="127.0.0.1", port=1080, kill_switch=False))
        settings = engine._session.get_settings()
        assert settings["anonymous_mode"] is True  # still the no-leak guarantee for peer/tracker
        assert settings["enable_dht"] is True
        assert settings["enable_lsd"] is True
        assert settings["enable_upnp"] is True
        assert settings["enable_natpmp"] is True
    finally:
        engine.shutdown()


def test_configure_privacy_none_restores_direct_connection(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        engine.configure_privacy(ProxyConfig(host="127.0.0.1", port=1080))
        engine.configure_privacy(None)
        settings = engine._session.get_settings()
        assert settings["proxy_type"] == int(lt.proxy_type_t.none)
        assert settings["anonymous_mode"] is False
        assert settings["enable_dht"] is True
        assert engine.privacy_status() == "disabled"
    finally:
        engine.shutdown()


def test_configure_privacy_empty_host_raises_proxy_config_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(ProxyConfigError):
            engine.configure_privacy(ProxyConfig(host="", port=1080))
    finally:
        engine.shutdown()


def test_configure_privacy_bad_port_raises_proxy_config_error(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(ProxyConfigError):
            engine.configure_privacy(ProxyConfig(host="127.0.0.1", port=70000))
        with pytest.raises(ProxyConfigError):
            engine.configure_privacy(ProxyConfig(host="127.0.0.1", port=0))
    finally:
        engine.shutdown()


def test_configure_privacy_invalid_config_does_not_change_applied_state(tmp_path: Path) -> None:
    """A rejected reconfiguration must not silently leave a half-applied state."""
    engine = _engine(tmp_path)
    try:
        engine.configure_privacy(ProxyConfig(host="127.0.0.1", port=1080))
        with pytest.raises(ProxyConfigError):
            engine.configure_privacy(ProxyConfig(host="", port=1080))
        assert engine.privacy_status() == "enabled"  # previous good config still applied
    finally:
        engine.shutdown()


def test_engine_applies_proxy_from_engine_config_at_construction(tmp_path: Path) -> None:
    config = EngineConfig(
        data_dir=tmp_path / "appdata", proxy=ProxyConfig(host="127.0.0.1", port=1080)
    )
    engine = TorrentEngine(config)
    try:
        assert engine.privacy_status() == "enabled"
        assert engine._session.get_settings()["proxy_hostname"] == "127.0.0.1"
    finally:
        engine.shutdown()


def test_set_listen_port_applies_live(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        engine.set_listen_port(7000)
        assert engine._session.get_settings()["listen_interfaces"] == "0.0.0.0:7000"
    finally:
        engine.shutdown()


def test_set_listen_port_out_of_range_raises(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        with pytest.raises(ValueError):
            engine.set_listen_port(0)
        with pytest.raises(ValueError):
            engine.set_listen_port(70000)
    finally:
        engine.shutdown()


# -- DHT peer probe (search-result detail view, v0.5.1a EXPERIMENTAL/ALPHA) --


class _FakeDhtSession:
    """Stand-in for ``lt.session`` inside :meth:`TorrentEngine.probe_dht_peers`.

    Mirrors ``_FakeAlertSession`` above (same rationale: ``lt.dht_get_peers_reply_alert``
    is a native-only type that can't be constructed from Python), but also
    carries ``get_settings()``/``dht_get_peers()`` so the whole method's flow
    -- not just its drain loop -- can be exercised without a live DHT.
    """

    def __init__(self, batches: list[list[object]], *, enable_dht: bool = True) -> None:
        self._batches = iter(batches)
        self._enable_dht = enable_dht
        self.dht_get_peers_calls: list[object] = []

    def get_settings(self) -> dict[str, object]:
        return {"enable_dht": self._enable_dht}

    def dht_get_peers(self, target: object) -> None:
        self.dht_get_peers_calls.append(target)

    def wait_for_alert(self, timeout_ms: int) -> None:
        return None

    def pop_alerts(self) -> list[object]:
        return next(self._batches, [])


def test_probe_dht_peers_returns_none_when_dht_disabled(tmp_path: Path) -> None:
    engine = _engine(tmp_path, enable_dht=False)
    try:
        start = time.monotonic()
        result = engine.probe_dht_peers(_BASE_HASH, timeout=5.0)
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed < 1.0  # short-circuited, never entered the drain loop
    finally:
        engine.shutdown()


def test_probe_dht_peers_returns_none_for_invalid_info_hash(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    try:
        assert engine.probe_dht_peers("not-a-valid-hex-hash", timeout=5.0) is None
    finally:
        engine.shutdown()


def test_probe_dht_peers_gives_up_at_the_timeout_when_nothing_arrives(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    real_session = engine._session
    try:
        engine._session = _FakeDhtSession([])  # never produces any alerts

        start = time.monotonic()
        result = engine.probe_dht_peers(_BASE_HASH, timeout=0.3)
        elapsed = time.monotonic() - start

        assert result is None
        assert elapsed >= 0.3
    finally:
        engine._session = real_session
        engine.shutdown()


def test_probe_dht_peers_returns_the_max_count_across_multiple_replies(tmp_path: Path) -> None:
    """A DHT lookup is answered by multiple nodes over its lifetime; the
    probe should report the highest peer count seen, not just the first."""
    engine = _engine(tmp_path)
    real_session = engine._session
    try:
        sentinel_low = object()
        sentinel_high = object()
        sentinel_unrelated = object()

        def fake_process(alert: object, target: object) -> int | None:
            if alert is sentinel_low:
                return 3
            if alert is sentinel_high:
                return 17
            return None

        engine._process_dht_peers_alert = fake_process  # type: ignore[method-assign]
        engine._session = _FakeDhtSession(
            [[sentinel_low, sentinel_unrelated], [sentinel_high]]
        )

        result = engine.probe_dht_peers(_BASE_HASH, timeout=0.3)

        assert result == 17
    finally:
        engine._session = real_session
        engine.shutdown()


def test_probe_dht_peers_requests_the_correct_target_hash(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    real_session = engine._session
    try:
        fake_session = _FakeDhtSession([])
        engine._session = fake_session

        engine.probe_dht_peers(_BASE_HASH, timeout=0.1)

        assert len(fake_session.dht_get_peers_calls) == 1
        assert str(fake_session.dht_get_peers_calls[0]) == _BASE_HASH
    finally:
        engine._session = real_session
        engine.shutdown()


def test_probe_dht_peers_on_closed_engine_returns_none(tmp_path: Path) -> None:
    engine = _engine(tmp_path)
    engine.shutdown()
    assert engine.probe_dht_peers(_BASE_HASH, timeout=1.0) is None


def test_blocking_flush_gives_up_at_the_timeout_when_nothing_arrives(tmp_path: Path) -> None:
    """If no alert ever arrives, the drain loop must give up at the timeout
    (not hang forever) and report zero saved."""
    engine = _engine(tmp_path)
    real_session = engine._session
    try:
        save_dir = tmp_path / "save"
        save_dir.mkdir()
        info_hash = engine.add_magnet(VALID_MAGNET, save_dir)
        handle = engine._get_handle(info_hash)

        engine._session = _FakeAlertSession([])  # never produces any alerts

        start = time.monotonic()
        saved_count = engine._blocking_flush([handle], timeout_s=0.3)
        elapsed = time.monotonic() - start

        assert saved_count == 0
        assert elapsed >= 0.3
    finally:
        engine._session = real_session
        engine.shutdown()
