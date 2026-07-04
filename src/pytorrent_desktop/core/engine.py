"""Torrent engine: a thin, GUI-independent facade over libtorrent.

This is the seam the whole app is built around. The GUI never talks to
libtorrent directly — it only calls :class:`TorrentEngine`. That keeps the
engine unit-testable without a display and lets us swap the polling loop for
an alert-driven one later without touching the UI.

v0.1.0 status ("engine foundation"): session lifecycle, add/pause/resume/
remove, the extended :class:`TorrentStatus` snapshot and the typed error
hierarchy (``core/errors.py``) are implemented against
docs/ARCHITECTURE.md.

v0.3.0 status ("persistence & sequential queue"): resume-data persistence
(§4.3, §5 — ``ResumeStore``, add-time/periodic/finished/shutdown saves) and
the sequential-queue auto-managed flow (§6) are implemented. The
SOCKS5/kill-switch privacy layer (v0.4) is still a type-only stub —
``configure_privacy``'s hook/structure is documented at its call site so that
milestone slots in without a facade change.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import libtorrent as lt

from .config import AppPaths, default_app_data_dir
from .errors import (
    DuplicateTorrentError,
    EngineInitError,
    InvalidMagnetError,
    SavePathError,
    TorrentFileError,
    UnknownTorrentError,
)
from .resume_store import ResumeStore

_log = logging.getLogger(__name__)

# libtorrent's numeric state -> human label. Mirrors lt.torrent_status.states.
# libtorrent 2.0 has no "error" or "queued"/"allocating" state member; errors
# are read from status().errc and queued/paused are conveyed via flags +
# queue_position (docs/ARCHITECTURE.md §3.1, §3.4).
_STATE_LABELS = {
    lt.torrent_status.checking_files: "checking",
    lt.torrent_status.downloading_metadata: "fetching metadata",
    lt.torrent_status.downloading: "downloading",
    lt.torrent_status.finished: "finished",
    lt.torrent_status.seeding: "seeding",
    lt.torrent_status.checking_resume_data: "checking resume data",
}


@dataclass(frozen=True)
class ProxyConfig:
    """SOCKS5 proxy settings (docs/ARCHITECTURE.md §3.3, §11).

    Type-only in v0.1.0: the dataclass is defined so the config surface is
    stable, but :meth:`TorrentEngine.configure_privacy` does not yet apply it
    to the session. Actual proxy/kill-switch wiring lands in v0.4.
    """

    host: str
    port: int
    username: str | None = None
    password: str | None = None
    kill_switch: bool = True


@dataclass(frozen=True)
class EngineConfig:
    """Construction-time settings for :class:`TorrentEngine` (§3.3).

    Replaces a bare ``listen_port`` int so packaging/tests can inject paths
    and the settings surface can grow without signature churn.
    """

    listen_port: int = 6881
    # Real per-user app-data root (docs/ARCHITECTURE.md §7), e.g.
    # ``%APPDATA%\pytorrent-desktop`` on Windows. Tests should override this
    # with ``tmp_path`` for isolation rather than relying on the real
    # location.
    data_dir: Path = field(default_factory=default_app_data_dir)
    enable_dht: bool = True
    proxy: ProxyConfig | None = None
    sequential_queue: bool = True


@dataclass(frozen=True)
class TorrentStatus:
    """A GUI-friendly, immutable snapshot of one torrent.

    Every field maps to a verified libtorrent 2.0.13 ``torrent_status``
    attribute (docs/ARCHITECTURE.md §3.1, docs/DECISIONS.md D4). No
    libtorrent type ever leaks out through this dataclass. ``frozen=True`` is
    kept so snapshots are safe to hand to a UI model as immutable value
    objects.
    """

    info_hash: str
    name: str
    save_path: str
    total_bytes: int
    downloaded_bytes: int
    progress: float  # 0.0 - 1.0
    download_rate: int  # bytes/s
    upload_rate: int  # bytes/s
    num_peers: int
    num_seeds: int
    state: str
    is_paused: bool
    is_finished: bool
    queue_position: int
    error: str | None


class TorrentEngine:
    """Owns the libtorrent session and every torrent handle.

    The facade is single-thread-affine: every method is meant to be called
    from the Qt main thread only (docs/ARCHITECTURE.md §3).
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        settings = {
            "user_agent": "pytorrent-desktop/0.1",
            "listen_interfaces": f"0.0.0.0:{self._config.listen_port}",
            "enable_dht": self._config.enable_dht,
            "alert_mask": lt.alert.category_t.all_categories,
        }
        try:
            self._session = lt.session(settings)
        except (RuntimeError, KeyError, TypeError) as exc:
            raise EngineInitError(f"Failed to start libtorrent session: {exc}") from exc

        # info_hash (hex; v1/v2/hybrid-aware, see _key_from_hashes) -> handle
        self._handles: dict[str, lt.torrent_handle] = {}
        self._closed = False
        # Stored for a future configure_privacy implementation (v0.4); not
        # applied to the session yet.
        self._proxy_config: ProxyConfig | None = self._config.proxy

        self._paths = AppPaths(self._config.data_dir)
        self._resume_store = ResumeStore(self._paths)
        self._last_periodic_resume_save = time.monotonic()

        # Sequential single-download queue (§6): active_downloads caps
        # concurrency; auto_managed (set on every add/load below) is what
        # makes a torrent participate in that queue at all.
        self.set_sequential_queue(self._config.sequential_queue)

        # Restore prior session state (§5.3) before the UI takes its first
        # snapshot() — no explicit UI action needed, restored torrents just
        # appear on the next poll.
        self._load_resume_data()

    # -- lifecycle ---------------------------------------------------------

    def describe(self) -> str:
        return f"libtorrent {lt.version}"

    def shutdown(self, timeout_s: float = 10.0) -> None:
        """Stop the session safely. Idempotent — safe to call more than once.

        Implements the full resume-data flush sequence (docs/ARCHITECTURE.md
        §4.3, the data-safety-critical path):

        1. ``session.pause()`` — stop new peer/piece activity.
        2. Request ``save_resume_data()`` (with ``save_info_dict`` +
           ``flush_disk_cache``, unconditionally — *not* gated by
           ``need_save_resume_data()``, which is only for periodic saves)
           for every valid handle.
        3. Block (up to ``timeout_s``) draining alerts via
           ``wait_for_alert``/``pop_alerts``, decrementing the outstanding
           count on *both* ``save_resume_data_alert`` and
           ``save_resume_data_failed_alert`` — failing to decrement on the
           failed alert is the documented way this hangs (e.g. a magnet still
           fetching metadata reliably fails the save, never succeeds).
        4. Log (don't raise) if anything is still outstanding at the
           deadline.
        5. Drop the session so its native threads join on destruction.
        """
        if self._closed:
            return
        self._session.pause()
        self._blocking_flush(list(self._handles.values()), timeout_s)
        self._closed = True
        del self._session

    def save_all_resume(self, timeout_s: float = 5.0) -> int:
        """Request + block for a resume-data save of every known torrent.

        Shares the drain loop with :meth:`shutdown` (§3.2's contract table)
        but does not pause the session or close it. Returns the number of
        torrents successfully saved before ``timeout_s`` elapsed.
        """
        return self._blocking_flush(list(self._handles.values()), timeout_s)

    # -- resume-data persistence (§4.3, §5) ---------------------------------

    # Full flags: include the info-dict (so magnet torrents that already
    # fetched metadata don't need to re-fetch it after a restart) and force a
    # disk-cache flush. Used for add-time / torrent-finished / shutdown
    # saves; periodic saves deliberately use plain ``save_resume_data()``
    # (no forced flush) gated by ``need_save_resume_data()`` instead, to keep
    # the 60s tick cheap (§4.3 "developer 핵심 규칙").
    _FULL_RESUME_FLAGS = lt.torrent_handle.save_info_dict | lt.torrent_handle.flush_disk_cache
    _PERIODIC_RESUME_INTERVAL_S = 60.0

    def _process_resume_alert(self, alert: object) -> Literal["saved", "failed"] | None:
        """Handle one alert if it's resume-related; else return ``None``.

        Shared by the non-blocking per-tick pump (:meth:`_pump_alerts`) and
        the blocking drain loop (:meth:`_blocking_flush`, used by both
        :meth:`shutdown` and :meth:`save_all_resume`) so the exact same
        save/failed handling backs both paths (docs/ARCHITECTURE.md §4.3,
        §5.1's "주기적 + 완료 시 저장은 종료 시와 동일한 알림 소비 경로를
        공유한다").
        """
        if isinstance(alert, lt.save_resume_data_alert):
            key = self._key_from_hashes(alert.params.info_hashes)
            buf = lt.write_resume_data_buf(alert.params)
            self._resume_store.save(key, buf)
            return "saved"
        if isinstance(alert, lt.save_resume_data_failed_alert):
            # Best-effort (docs/ARCHITECTURE.md §8): log and move on. This is
            # the expected outcome for e.g. a magnet torrent that has no
            # metadata yet — it must still count against "outstanding" or
            # shutdown hangs to its timeout.
            _log.warning("Resume data save failed: %s", alert.error.message())
            return "failed"
        return None

    def _blocking_flush(self, handles: list[lt.torrent_handle], timeout_s: float) -> int:
        """Request a full resume-data save for ``handles`` and block for it.

        Implements docs/ARCHITECTURE.md §4.3 steps 3-5: request, then poll
        ``wait_for_alert``/``pop_alerts`` up to ``timeout_s``, decrementing
        the outstanding count on *both* success and failure so a torrent that
        can never produce a real resume blob (e.g. metadata-less magnet)
        cannot block the whole drain until the deadline. Returns the number
        of torrents actually saved.
        """
        outstanding = 0
        saved = 0
        for handle in handles:
            if not handle.is_valid():
                continue
            handle.save_resume_data(self._FULL_RESUME_FLAGS)
            outstanding += 1

        deadline = time.monotonic() + timeout_s
        while outstanding > 0 and time.monotonic() < deadline:
            self._session.wait_for_alert(200)  # ms; blocks up to the next alert batch
            for alert in self._session.pop_alerts():
                kind = self._process_resume_alert(alert)
                if kind == "saved":
                    outstanding -= 1
                    saved += 1
                elif kind == "failed":
                    outstanding -= 1

        if outstanding > 0:
            _log.warning("%d torrent(s) did not flush resume data before the timeout", outstanding)
        return saved

    def _pump_alerts(self) -> None:
        """Non-blocking alert drain, called once per poll tick from :meth:`snapshot`.

        docs/ARCHITECTURE.md §4.2's polling model has no dedicated alert
        thread, so alerts (torrent-finished, resume saves requested
        add-time/periodically) are consumed here rather than in a loop of
        their own — this keeps the facade single-threaded and synchronous.
        """
        for alert in self._session.pop_alerts():
            if self._process_resume_alert(alert) is not None:
                continue
            if isinstance(alert, lt.torrent_finished_alert) and alert.handle.is_valid():
                # A finished torrent should resume as seeding, not re-check,
                # on the next start (§5.1 item 3).
                alert.handle.save_resume_data(self._FULL_RESUME_FLAGS)

    def _periodic_resume_save_if_due(self) -> None:
        """Every 60s, ask each modified handle to save resume data (§5.1 item 2).

        Gated by ``need_save_resume_data()`` per handle (rather than always
        saving, or passing the ``only_if_modified`` flag) so an idle torrent
        with nothing new since the last save costs nothing.
        """
        now = time.monotonic()
        if now - self._last_periodic_resume_save < self._PERIODIC_RESUME_INTERVAL_S:
            return
        self._last_periodic_resume_save = now
        for handle in self._handles.values():
            if handle.is_valid() and handle.need_save_resume_data():
                handle.save_resume_data()

    def _load_resume_data(self) -> None:
        """Startup: restore every persisted torrent from ``resume/*.fastresume`` (§5.3).

        Corrupt/unparseable files are already quarantined by
        ``ResumeStore.load_all``. Every restored torrent is (re-)added
        auto-managed regardless of the persisted flags, so it participates
        in the sequential queue the same as a freshly-added torrent (§6); its
        persisted ``queue_position`` and paused state are preserved by
        libtorrent's own resume-data round trip.
        """
        for atp in self._resume_store.load_all():
            if not atp.save_path:
                # Defensive: should not happen (save_path is always set at
                # add time), but a blank path would otherwise raise deep
                # inside libtorrent. Fall back to a sane default rather than
                # dropping the torrent.
                atp.save_path = str(Path.home() / "Downloads")
            atp.flags |= lt.torrent_flags.auto_managed
            try:
                handle = self._session.add_torrent(atp)
            except RuntimeError as exc:  # pragma: no cover - defensive
                _log.warning("Could not restore torrent from resume data: %s", exc)
                continue
            key = self._key_from_hashes(atp.info_hashes)
            self._register(key, handle)

    # -- identity ------------------------------------------------------------

    @staticmethod
    def _key_from_hashes(info_hashes: lt.info_hash_t) -> str:
        """Stable identity string from an ``info_hash_t`` (v1/v2/hybrid).

        Uses ``get_best()`` (the v2 hash when the torrent has one, otherwise
        v1) rather than the deprecated v1-only ``info_hash()``, so duplicate
        detection and resume-file keying are correct for v2/hybrid torrents
        (docs/ARCHITECTURE.md §3.5, docs/DECISIONS.md D5). This is the single
        helper to change if the keying strategy ever needs to change again.
        """
        return str(info_hashes.get_best())

    def _key(self, handle: lt.torrent_handle) -> str:
        return self._key_from_hashes(handle.info_hashes())

    def _register(self, key: str, handle: lt.torrent_handle) -> str:
        self._handles[key] = handle
        return key

    def _get_handle(self, info_hash: str) -> lt.torrent_handle:
        try:
            return self._handles[info_hash]
        except KeyError:
            raise UnknownTorrentError(info_hash) from None

    def _validate_save_path(self, save_path: str | Path) -> Path:
        path = Path(save_path)
        if not path.is_dir():
            raise SavePathError(f"Save path does not exist or is not a directory: {path}")
        if not os.access(path, os.W_OK):
            raise SavePathError(f"Save path is not writable: {path}")
        return path

    # -- adding ------------------------------------------------------------

    def add_torrent_file(self, torrent_path: str | Path, save_path: str | Path) -> str:
        """Add a torrent from a local ``.torrent`` file.

        Raises ``TorrentFileError`` (alias of ``InvalidTorrentError``) if the
        file is missing or unparsable, ``SavePathError`` if ``save_path`` is
        missing/not writable, and ``DuplicateTorrentError`` if this
        info-hash is already known.
        """
        path = Path(torrent_path)
        if not path.is_file():
            raise TorrentFileError(f"Torrent file not found: {path}")
        try:
            info = lt.torrent_info(str(path))
        except (RuntimeError, OSError) as exc:
            raise TorrentFileError(f"Could not parse torrent file: {path}") from exc

        key = self._key_from_hashes(info.info_hashes())
        if key in self._handles:
            raise DuplicateTorrentError(key)

        save_dir = self._validate_save_path(save_path)
        params = lt.add_torrent_params()
        params.ti = info
        params.save_path = str(save_dir)
        # Every torrent must be auto-managed to participate in the
        # sequential queue (§6) — active_downloads only constrains
        # auto-managed torrents.
        params.flags |= lt.torrent_flags.auto_managed
        handle = self._session.add_torrent(params)
        self._register(key, handle)
        self._request_resume_save(handle)  # §5.1 item 1: save once, right after adding
        return key

    def add_magnet(self, magnet_uri: str, save_path: str | Path) -> str:
        """Add a torrent from a magnet URI.

        Raises ``InvalidMagnetError`` if the URI can't be parsed,
        ``SavePathError`` if ``save_path`` is missing/not writable, and
        ``DuplicateTorrentError`` if this info-hash is already known.

        The duplicate check happens *before* calling into libtorrent: adding
        the same info-hash twice does not raise there (it silently returns
        the existing handle), so ``self._handles`` is the source of truth for
        duplicates (docs/ARCHITECTURE.md §8).
        """
        try:
            params = lt.parse_magnet_uri(magnet_uri)
        except (RuntimeError, TypeError) as exc:
            raise InvalidMagnetError(f"Invalid magnet URI: {magnet_uri!r}") from exc

        key = self._key_from_hashes(params.info_hashes)
        if key in self._handles:
            raise DuplicateTorrentError(key)

        save_dir = self._validate_save_path(save_path)
        params.save_path = str(save_dir)
        params.flags |= lt.torrent_flags.auto_managed

        handle = self._session.add_torrent(params)
        self._register(key, handle)
        self._request_resume_save(handle)  # §5.1 item 1
        return key

    def _request_resume_save(self, handle: lt.torrent_handle) -> None:
        """Fire-and-forget resume-data request; the resulting alert is
        collected on the next :meth:`_pump_alerts` (or the shutdown/
        save_all_resume drain, whichever comes first)."""
        if handle.is_valid():
            handle.save_resume_data(self._FULL_RESUME_FLAGS)

    # -- control -----------------------------------------------------------

    def pause(self, info_hash: str) -> None:
        self._get_handle(info_hash).pause()

    def resume(self, info_hash: str) -> None:
        self._get_handle(info_hash).resume()

    def remove(self, info_hash: str, *, delete_data: bool = False) -> None:
        handle = self._get_handle(info_hash)
        del self._handles[info_hash]
        flags = lt.session.delete_files if delete_data else 0
        self._session.remove_torrent(handle, flags)
        # Otherwise a stale resume file would resurrect this torrent on the
        # next startup (§5.3 loads every *.fastresume unconditionally).
        self._resume_store.delete(info_hash)

    # -- status ------------------------------------------------------------

    def snapshot(self) -> list[TorrentStatus]:
        """Return a status snapshot for every torrent (called ~1x/sec by the UI).

        Never raises: a torrent that has a fatal libtorrent-side error still
        yields a row, with ``TorrentStatus.error`` set (docs/ARCHITECTURE.md
        §8, §3.1).

        Also drives the alert pump and the 60s periodic resume save
        (docs/ARCHITECTURE.md §4.2's "성능 가드" / §5.1 item 2) — the polling
        model has no dedicated alert thread, so this is where alerts
        (resume saves, torrent-finished) get consumed, once per tick.
        """
        self._pump_alerts()
        self._periodic_resume_save_if_due()

        result: list[TorrentStatus] = []
        for info_hash, handle in self._handles.items():
            if not handle.is_valid():
                continue
            s = handle.status()
            error = str(s.errc.message()) if s.errc.value() else None
            is_finished = s.progress >= 1.0 or s.state in (
                lt.torrent_status.finished,
                lt.torrent_status.seeding,
            )
            result.append(
                TorrentStatus(
                    info_hash=info_hash,
                    name=s.name or "(fetching metadata…)",
                    save_path=s.save_path,
                    total_bytes=s.total_wanted,
                    downloaded_bytes=s.total_wanted_done,
                    progress=s.progress,
                    download_rate=s.download_rate,
                    upload_rate=s.upload_rate,
                    num_peers=s.num_peers,
                    num_seeds=s.num_seeds,
                    state=_STATE_LABELS.get(s.state, str(s.state)),
                    is_paused=bool(s.flags & lt.torrent_flags.paused),
                    is_finished=is_finished,
                    queue_position=s.queue_position,
                    error=error,
                )
            )
        return result

    # -- queue (feature #6) -------------------------------------------------

    _QUEUE_MOVE_METHODS = {
        "up": "queue_position_up",
        "down": "queue_position_down",
        "top": "queue_position_top",
        "bottom": "queue_position_bottom",
    }

    def set_sequential_queue(self, one_at_a_time: bool) -> None:
        """Download one torrent at a time, then the next (docs/ARCHITECTURE.md §6).

        ``active_downloads=1`` is the actual concurrency cap; toggling it off
        sets ``-1`` (unlimited). ``active_limit`` is raised well above any
        realistic torrent count so it never becomes the *binding* constraint
        in either mode, and ``dont_count_slow_torrents`` keeps a stalled
        (peerless) torrent from permanently occupying the single active
        slot. All three keys are set explicitly (rather than relying on
        libtorrent's current defaults, which happen to already match) so
        behavior doesn't drift if the bundled libtorrent version changes its
        defaults.

        Every torrent is added/restored auto-managed (see ``add_magnet``,
        ``add_torrent_file``, ``_load_resume_data``) regardless of this
        toggle — only auto-managed torrents are subject to
        ``active_downloads`` at all, so this setting is what actually turns
        the queue into "one at a time" vs. "unlimited concurrent".
        """
        self._session.apply_settings(
            {
                "active_downloads": 1 if one_at_a_time else -1,
                "active_limit": 500,
                "dont_count_slow_torrents": True,
            }
        )

    def move_in_queue(
        self, info_hash: str, direction: Literal["up", "down", "top", "bottom"]
    ) -> None:
        """Reorder ``info_hash`` in the sequential queue (§6).

        Maps directly to ``handle.queue_position_up/down/top/bottom()``. The
        next ``snapshot()`` reflects the new ``queue_position`` — no manual
        model bookkeeping needed on the UI side.
        """
        handle = self._get_handle(info_hash)
        method_name = self._QUEUE_MOVE_METHODS[direction]
        getattr(handle, method_name)()

    # -- privacy (feature #5) ------------------------------------------------

    def configure_privacy(self, cfg: ProxyConfig | None) -> None:
        """Route all traffic through a user-supplied SOCKS5 proxy, or disable it.

        TODO(v0.4): implement per docs/ARCHITECTURE.md §11 — validate
        ``cfg.host``/``cfg.port`` (raise ``ProxyConfigError`` on bad input),
        then ``apply_settings`` with ``anonymous_mode`` + ``proxy_hostnames``
        as the load-bearing no-leak guarantee, and disable DHT/LSD/UPnP/
        NAT-PMP when ``cfg.kill_switch`` is on (docs/DECISIONS.md D1). Left
        as a type-only stub for v0.1.0: the shape of ``ProxyConfig`` is
        finalized, but nothing is applied to the session yet.
        """
        self._proxy_config = cfg
