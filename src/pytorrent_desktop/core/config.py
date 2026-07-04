"""Filesystem locations for persisted application state (docs/ARCHITECTURE.md §7).

Centralized here so tests can inject an isolated root (e.g. ``tmp_path``) and
packaging never needs write access to the (possibly read-only) install
directory: PyInstaller's ``dist/`` folder can live under ``Program Files``,
but ``%APPDATA%`` is always writable for the current user.

``core/`` has no Qt imports (docs/ARCHITECTURE.md §1) — this module only
touches ``os``/``pathlib``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

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
