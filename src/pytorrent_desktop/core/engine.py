"""Torrent engine: a thin, GUI-independent facade over libtorrent.

This is the seam the whole app is built around. The GUI never talks to
libtorrent directly — it only calls :class:`TorrentEngine`. That keeps the
engine unit-testable without a display and lets us swap the polling loop for
an alert-driven one later without touching the UI.

v0.1.0 status ("engine foundation"): session lifecycle, add/pause/resume/
remove, the extended :class:`TorrentStatus` snapshot and the typed error
hierarchy (``core/errors.py``) are implemented against
docs/ARCHITECTURE.md. Resume-data persistence and the sequential-queue
auto-managed flow (v0.3) and the SOCKS5/kill-switch privacy layer (v0.4) are
intentionally left as stubs — their hooks/structure are documented at the
call sites below so the next milestone slots in without a facade change.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import libtorrent as lt

from .errors import (
    DuplicateTorrentError,
    EngineInitError,
    InvalidMagnetError,
    SavePathError,
    TorrentFileError,
    UnknownTorrentError,
)

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
    # Placeholder default: no AppPaths/config.py yet (that lands with
    # ResumeStore/ConfigStore in a later milestone — docs/ARCHITECTURE.md
    # §7). Nothing in v0.1.0 reads or writes under data_dir; it is carried
    # here so callers who build a real AppPaths can inject it today.
    data_dir: Path = field(
        default_factory=lambda: Path(tempfile.gettempdir()) / "pytorrent-desktop"
    )
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

    # -- lifecycle ---------------------------------------------------------

    def describe(self) -> str:
        return f"libtorrent {lt.version}"

    def shutdown(self, timeout_s: float = 10.0) -> None:
        """Stop the session safely. Idempotent — safe to call more than once.

        v0.1.0 scope: pause the session so no new peer/piece activity occurs.
        The full resume-data flush sequence (docs/ARCHITECTURE.md §4.3:
        ``handle.save_resume_data()`` per handle, then draining
        ``save_resume_data_alert`` / ``save_resume_data_failed_alert`` up to
        ``timeout_s`` and persisting via ``ResumeStore``) is the data-safety
        seam reserved for v0.3, alongside the ``ResumeStore`` it depends on.
        Do not add a partial flush here — an incomplete drain loop that
        forgets to decrement on the *failed* alert is the documented way this
        hangs; it belongs with the real ``ResumeStore``.
        """
        if self._closed:
            return
        self._session.pause()
        self._closed = True

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
        handle = self._session.add_torrent({"ti": info, "save_path": str(save_dir)})
        return self._register(key, handle)

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

        handle = self._session.add_torrent(params)
        return self._register(key, handle)

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

    # -- status ------------------------------------------------------------

    def snapshot(self) -> list[TorrentStatus]:
        """Return a status snapshot for every torrent (called ~1x/sec by the UI).

        Never raises: a torrent that has a fatal libtorrent-side error still
        yields a row, with ``TorrentStatus.error`` set (docs/ARCHITECTURE.md
        §8, §3.1).
        """
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

    def set_sequential_queue(self, one_at_a_time: bool) -> None:
        """Download one torrent at a time, then the next.

        libtorrent already implements this via queue management: cap the
        number of simultaneously active downloads and let auto-managed
        torrents queue by position.

        TODO(v0.3): also ensure new torrents are added auto-managed and
        expose queue reordering (``move_in_queue`` /
        ``queue_position_up/down/top/bottom``) — docs/ARCHITECTURE.md §6.
        Left as-is for v0.1.0; only ``active_downloads`` is toggled here.
        """
        self._session.apply_settings({"active_downloads": 1 if one_at_a_time else -1})

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
