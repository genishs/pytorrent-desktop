"""Filesystem locations and persisted app settings (docs/ARCHITECTURE.md §7).

Centralized here so tests can inject an isolated root (e.g. ``tmp_path``) and
packaging never needs write access to the (possibly read-only) install
directory: PyInstaller's ``dist/`` folder can live under ``Program Files``,
but ``%APPDATA%`` is always writable for the current user.

``core/`` has no Qt imports (docs/ARCHITECTURE.md §1) — this module only
touches ``os``/``json``/``pathlib``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

_log = logging.getLogger(__name__)

_APP_DIR_NAME = "pytorrent-desktop"


def default_app_data_dir() -> Path:
    """Resolve the real per-user application data root.

    - **Windows** (the primary target platform, docs/ARCHITECTURE.md §1, §7):
      ``%APPDATA%\\pytorrent-desktop`` i.e. ``os.environ["APPDATA"]`` joined
      with the app name.
    - **Other platforms** (CI runs both Ubuntu and Windows — see
      ``.github/workflows/ci.yml`` — and developers may run the test suite on
      Linux/macOS): fall back to ``$XDG_DATA_HOME/pytorrent-desktop`` or
      ``~/.local/share/pytorrent-desktop`` so there is still a sane, writable
      per-user home instead of raising or writing into a temp dir that
      silently disappears.

    Tests that need isolation should construct ``EngineConfig(data_dir=...)``
    / ``AppPaths(data_dir=...)`` explicitly with ``tmp_path`` rather than
    relying on (or monkeypatching) this default.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / _APP_DIR_NAME
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    if xdg_data_home:
        return Path(xdg_data_home) / _APP_DIR_NAME
    return Path.home() / ".local" / "share" / _APP_DIR_NAME


@dataclass(frozen=True)
class AppPaths:
    """Resolved data directories, all rooted under ``data_dir`` (§7).

    ``data_dir`` defaults to :func:`default_app_data_dir`; construct with an
    explicit path (e.g. ``tmp_path`` in tests) for isolation.
    """

    data_dir: Path = field(default_factory=default_app_data_dir)

    @property
    def resume_dir(self) -> Path:
        """One ``<info_hash>.fastresume`` file per torrent (§5.1, §7)."""
        return self.data_dir / "resume"

    @property
    def resume_quarantine_dir(self) -> Path:
        """Unparseable/corrupt resume files land here instead of being deleted (§5.3)."""
        return self.resume_dir / "bad"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    def ensure(self) -> None:
        """Create the on-disk directory tree if it doesn't exist yet. Idempotent."""
        self.resume_quarantine_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


def default_download_dir() -> Path:
    """Default save path shown the first time Settings is opened (docs/UX-SPEC.md §4).

    ``%USERPROFILE%\\Downloads\\pytorrent-desktop`` (created on demand by the
    caller, not here — this module only computes paths).
    """
    return Path.home() / "Downloads" / _APP_DIR_NAME


# -- persisted app settings (v0.4.0, §7's config.json schema) ----------------

_SCHEMA_VERSION = 1
_ON_COMPLETE_ACTIONS = ("none", "quit_app", "shutdown_system")

OnCompleteAction = Literal["none", "quit_app", "shutdown_system"]


@dataclass(frozen=True)
class ProxySettings:
    """The persisted subset of SOCKS5 proxy configuration.

    **Deliberately has no password field** (docs/DECISIONS.md D2): the
    SOCKS5 password is kept in memory only by the UI layer and is never
    written to ``config.json``. ``TorrentEngine.ProxyConfig`` is the
    superset that also carries a password, built by the caller at
    apply-time from this plus whatever the user has typed in this run.
    """

    enabled: bool = False
    host: str = ""
    port: int = 1080
    username: str | None = None
    kill_switch: bool = True


@dataclass(frozen=True)
class OnCompleteSettings:
    """docs/DECISIONS.md D3: opt-in, defaults to ``"none"``."""

    action: OnCompleteAction = "none"


@dataclass(frozen=True)
class AppSettings:
    """The full ``config.json`` schema (docs/ARCHITECTURE.md §7), as a value object.

    ``schema_version`` is carried through so a future migration has
    somewhere to branch on; this milestone only ever writes/reads version 1.
    """

    schema_version: int = _SCHEMA_VERSION
    listen_port: int = 6881
    default_save_path: str = field(default_factory=lambda: str(default_download_dir()))
    sequential_queue: bool = True
    proxy: ProxySettings = field(default_factory=ProxySettings)
    on_complete: OnCompleteSettings = field(default_factory=OnCompleteSettings)


class ConfigStore:
    """Reads/writes ``config.json`` (docs/ARCHITECTURE.md §7).

    Mirrors :class:`~pytorrent_desktop.core.resume_store.ResumeStore`'s
    safety properties: atomic tmp-then-``os.replace`` writes, and a load path
    that never raises — a missing or corrupt ``config.json`` falls back to
    :class:`AppSettings` defaults rather than blocking startup, the same
    precedent as §5.3's quarantine-corrupt-resume-files behavior.
    """

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths

    def load(self) -> AppSettings:
        """Return the persisted settings, or defaults if missing/unreadable."""
        path = self._paths.config_path
        if not path.is_file():
            return AppSettings()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            return self._from_dict(raw)
        except (json.JSONDecodeError, TypeError, ValueError, OSError) as exc:
            _log.warning("Could not parse %s, falling back to defaults: %s", path, exc)
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        """Atomically write ``settings`` (§5.2's tmp + ``os.replace`` pattern).

        Only ``proxy.username`` round-trips through this file, never a
        password (D2) — the caller (``MainWindow``) must not put one on
        ``settings.proxy`` in the first place, since :class:`ProxySettings`
        has no such field to begin with.
        """
        self._paths.ensure()
        path = self._paths.config_path
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(
            json.dumps(self._to_dict(settings), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)

    @staticmethod
    def _to_dict(settings: AppSettings) -> dict:
        return {
            "schema_version": settings.schema_version,
            "listen_port": settings.listen_port,
            "default_save_path": settings.default_save_path,
            "sequential_queue": settings.sequential_queue,
            "proxy": {
                "enabled": settings.proxy.enabled,
                "host": settings.proxy.host,
                "port": settings.proxy.port,
                "username": settings.proxy.username,
                "kill_switch": settings.proxy.kill_switch,
            },
            "on_complete": {"action": settings.on_complete.action},
        }

    @staticmethod
    def _from_dict(raw: dict) -> AppSettings:
        defaults = AppSettings()
        proxy_raw = raw.get("proxy") or {}
        on_complete_raw = raw.get("on_complete") or {}

        action = on_complete_raw.get("action", defaults.on_complete.action)
        if action not in _ON_COMPLETE_ACTIONS:
            action = "none"

        return AppSettings(
            schema_version=int(raw.get("schema_version", defaults.schema_version)),
            listen_port=int(raw.get("listen_port", defaults.listen_port)),
            default_save_path=str(raw.get("default_save_path", defaults.default_save_path)),
            sequential_queue=bool(raw.get("sequential_queue", defaults.sequential_queue)),
            proxy=ProxySettings(
                enabled=bool(proxy_raw.get("enabled", defaults.proxy.enabled)),
                host=str(proxy_raw.get("host", defaults.proxy.host)),
                port=int(proxy_raw.get("port", defaults.proxy.port)),
                username=proxy_raw.get("username", defaults.proxy.username),
                kill_switch=bool(proxy_raw.get("kill_switch", defaults.proxy.kill_switch)),
            ),
            on_complete=OnCompleteSettings(action=action),
        )
