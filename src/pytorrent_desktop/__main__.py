"""Application entry point.

The GUI (PySide6) lives in ``pytorrent_desktop.ui`` and the torrent engine
(GUI-independent, wrapping libtorrent) lives in ``pytorrent_desktop.core``.
This entry point wires them together. During early scaffolding it only proves
the package is installed and the engine imports; the window is built next.
"""

from __future__ import annotations


def main() -> None:
    from pytorrent_desktop import __version__

    # Import here so a missing native dependency surfaces a clear message
    # rather than failing at module import time.
    try:
        from pytorrent_desktop.core.engine import TorrentEngine
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise SystemExit(f"Failed to initialize torrent engine: {exc}") from exc

    engine = TorrentEngine()
    print(f"pytorrent-desktop {__version__} - engine ready ({engine.describe()}).")
    print("GUI implementation in progress. See docs/SCOPE.md.")
    engine.shutdown()


if __name__ == "__main__":
    main()
