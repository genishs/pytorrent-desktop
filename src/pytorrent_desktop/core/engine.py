"""Torrent engine: a thin, GUI-independent facade over libtorrent.

This is the seam the whole app is built around. The GUI never talks to
libtorrent directly — it only calls :class:`TorrentEngine`. That keeps the
engine unit-testable without a display and lets us swap the polling loop for
an alert-driven one later without touching the UI.

Scaffold status: session setup, add/pause/resume/remove and status polling are
wired to real libtorrent calls. Resume-data persistence, the SOCKS5/kill-switch
privacy layer and the sequential queue toggle are stubbed with clear TODOs for
the developer to complete against docs/SCOPE.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import libtorrent as lt

# libtorrent's numeric state -> human label. Mirrors lt.torrent_status.states.
_STATE_LABELS = {
    lt.torrent_status.checking_files: "checking",
    lt.torrent_status.downloading_metadata: "fetching metadata",
    lt.torrent_status.downloading: "downloading",
    lt.torrent_status.finished: "finished",
    lt.torrent_status.seeding: "seeding",
    lt.torrent_status.checking_resume_data: "checking resume data",
}


@dataclass(frozen=True)
class TorrentStatus:
    """A GUI-friendly snapshot of one torrent. No libtorrent types leak out."""

    info_hash: str
    name: str
    total_bytes: int
    progress: float  # 0.0 - 1.0
    download_rate: int  # bytes/s
    upload_rate: int  # bytes/s
    num_peers: int
    state: str
    is_paused: bool


class TorrentEngine:
    """Owns the libtorrent session and every torrent handle."""

    def __init__(self, listen_port: int = 6881) -> None:
        self._session = lt.session(
            {
                "user_agent": "pytorrent-desktop/0.1",
                "listen_interfaces": f"0.0.0.0:{listen_port}",
                "enable_dht": True,
                "alert_mask": lt.alert.category_t.all_categories,
            }
        )
        # info_hash (hex) -> handle
        self._handles: dict[str, lt.torrent_handle] = {}

    # -- lifecycle ---------------------------------------------------------

    def describe(self) -> str:
        return f"libtorrent {lt.version}"

    def shutdown(self) -> None:
        """Pause the session so a final resume-data flush can happen.

        TODO(developer): before returning, request and persist resume data for
        every handle (save_resume_data + wait for save_resume_data_alert) so an
        in-progress download resumes on next launch. This is a known data-loss
        seam flagged in the plan — cover it with the shutdown sequence.
        """
        self._session.pause()

    # -- adding ------------------------------------------------------------

    def add_torrent_file(self, torrent_path: str | Path, save_path: str | Path) -> str:
        info = lt.torrent_info(str(torrent_path))
        handle = self._session.add_torrent({"ti": info, "save_path": str(save_path)})
        return self._register(handle)

    def add_magnet(self, magnet_uri: str, save_path: str | Path) -> str:
        params = lt.parse_magnet_uri(magnet_uri)
        params.save_path = str(save_path)
        handle = self._session.add_torrent(params)
        return self._register(handle)

    def _register(self, handle: lt.torrent_handle) -> str:
        info_hash = str(handle.info_hash())
        self._handles[info_hash] = handle
        return info_hash

    # -- control -----------------------------------------------------------

    def pause(self, info_hash: str) -> None:
        self._handles[info_hash].pause()

    def resume(self, info_hash: str) -> None:
        self._handles[info_hash].resume()

    def remove(self, info_hash: str, *, delete_data: bool = False) -> None:
        handle = self._handles.pop(info_hash)
        flags = lt.session.delete_files if delete_data else 0
        self._session.remove_torrent(handle, flags)

    # -- status ------------------------------------------------------------

    def snapshot(self) -> list[TorrentStatus]:
        """Return a status snapshot for every torrent (called ~1x/sec by the UI)."""
        result: list[TorrentStatus] = []
        for info_hash, handle in self._handles.items():
            s = handle.status()
            result.append(
                TorrentStatus(
                    info_hash=info_hash,
                    name=s.name or "(fetching metadata…)",
                    total_bytes=s.total_wanted,
                    progress=s.progress,
                    download_rate=s.download_rate,
                    upload_rate=s.upload_rate,
                    num_peers=s.num_peers,
                    state=_STATE_LABELS.get(s.state, str(s.state)),
                    is_paused=s.flags & lt.torrent_flags.paused != 0,
                )
            )
        return result

    # -- queue (feature #6) ------------------------------------------------

    def set_sequential_queue(self, one_at_a_time: bool) -> None:
        """Download one torrent at a time, then the next.

        libtorrent already implements this via queue management: cap the number
        of simultaneously active downloads and let auto-managed torrents queue
        by position.

        TODO(developer): also ensure new torrents are added auto-managed and
        expose queue reordering (queue_position_up/down) in the UI.
        """
        self._session.apply_settings({"active_downloads": 1 if one_at_a_time else -1})

    # -- privacy (feature #5) ---------------------------------------------

    def configure_privacy(
        self, *, socks5_host: str, socks5_port: int, kill_switch: bool = True
    ) -> None:
        """Route all traffic through a user-supplied SOCKS5 proxy.

        TODO(developer): wire this to the settings dialog. ``anonymous_mode``
        forces connections through the proxy and strips identifying info; the
        kill switch means we must NOT fall back to direct connections when the
        proxy is down (verify no leak on proxy failure before shipping).
        """
        self._session.apply_settings(
            {
                "proxy_type": lt.proxy_type_t.socks5,
                "proxy_hostname": socks5_host,
                "proxy_port": socks5_port,
                "anonymous_mode": True,
                "proxy_peer_connections": True,
                "proxy_tracker_connections": True,
                # Kill switch: with anonymous_mode + proxied connections, a dead
                # proxy simply yields no peers rather than leaking direct.
                "force_proxy": kill_switch,
            }
        )
