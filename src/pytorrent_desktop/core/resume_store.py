"""Resume-data persistence: one bencoded ``.fastresume`` file per torrent.

docs/ARCHITECTURE.md §5. This module owns the on-disk round trip only — it
never inspects the *contents* of a resume blob beyond what libtorrent's own
``read_resume_data``/``write_resume_data_buf`` need to round-trip an
``add_torrent_params``. Keying is delegated to the caller (``TorrentEngine``,
via ``_key_from_hashes`` — docs/DECISIONS.md D5) so this store has no opinion
about v1/v2/hybrid info-hashes.

``core/`` has no Qt imports; this module is exercised headless in tests.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import libtorrent as lt

from .config import AppPaths

_log = logging.getLogger(__name__)

_SUFFIX = ".fastresume"


class ResumeStore:
    """Reads/writes ``<info_hash>.fastresume`` files under ``resume_dir``."""

    def __init__(self, paths: AppPaths) -> None:
        self._paths = paths
        self._paths.ensure()

    # -- paths ---------------------------------------------------------

    def path_for(self, key: str) -> Path:
        return self._paths.resume_dir / f"{key}{_SUFFIX}"

    # -- writing ---------------------------------------------------------

    def save(self, key: str, buf: bytes) -> None:
        """Atomically write ``buf`` (a bencoded resume blob) for ``key``.

        Writes to a ``.tmp`` sibling then ``os.replace()``s it into place
        (§5.2) — ``os.replace`` is atomic on Windows/NTFS, so a crash mid-write
        can never corrupt a previously-good resume file.
        """
        target = self.path_for(key)
        tmp_path = target.with_suffix(target.suffix + ".tmp")
        tmp_path.write_bytes(buf)
        os.replace(tmp_path, target)

    def delete(self, key: str) -> None:
        """Remove the resume file for ``key``, if present.

        Called when a torrent is removed from the engine — otherwise a stale
        resume file would resurrect a removed torrent on the next startup.
        Missing files are not an error (idempotent, mirrors the removal it
        backs).
        """
        try:
            self.path_for(key).unlink()
        except FileNotFoundError:
            pass

    # -- loading (startup, §5.3) ------------------------------------------

    def load_all(self) -> list[lt.add_torrent_params]:
        """Parse every ``*.fastresume`` file into ``add_torrent_params``.

        Files that fail to parse (corrupt, truncated, or an old/foreign
        format) are quarantined into ``resume/bad/`` rather than deleted —
        recoverable, and never blocks startup (§5.3).
        """
        results: list[lt.add_torrent_params] = []
        for f in sorted(self._paths.resume_dir.glob(f"*{_SUFFIX}")):
            try:
                buf = f.read_bytes()
                atp = lt.read_resume_data(buf)
            except Exception as exc:  # noqa: BLE001 - any parse/IO failure quarantines
                _log.warning("Quarantining unreadable resume file %s: %s", f, exc)
                self._quarantine(f)
                continue
            results.append(atp)
        return results

    def _quarantine(self, f: Path) -> None:
        target = self._paths.resume_quarantine_dir / f.name
        if target.exists():
            target = self._paths.resume_quarantine_dir / f"{f.stem}.{int(time.time())}{f.suffix}"
        try:
            os.replace(f, target)
        except OSError as exc:  # pragma: no cover - defensive; best-effort
            _log.warning("Could not quarantine resume file %s: %s", f, exc)
