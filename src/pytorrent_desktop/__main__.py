"""Application entry point.

The GUI (PySide6) lives in ``pytorrent_desktop.ui`` and the torrent engine
(GUI-independent, wrapping libtorrent) lives in ``pytorrent_desktop.core``.
This wires them together: build the engine, build the ``QApplication`` and
:class:`~pytorrent_desktop.ui.main_window.MainWindow`, load an optional
stylesheet, run the event loop, then flush the engine on the way out
(docs/ARCHITECTURE.md §4.3 — resume-data safety on shutdown).
"""

from __future__ import annotations

import sys
from pathlib import Path

_STYLES_PATH = Path(__file__).parent / "ui" / "styles.qss"


def main() -> int:
    from PySide6.QtWidgets import QApplication

    # Import here so a missing native dependency surfaces a clear message
    # rather than failing at module import time.
    try:
        from pytorrent_desktop.core.engine import TorrentEngine
    except Exception as exc:  # pragma: no cover - diagnostic path
        raise SystemExit(f"Failed to initialize torrent engine: {exc}") from exc

    from pytorrent_desktop.ui.main_window import MainWindow

    app = QApplication(sys.argv)

    # Optional stylesheet: absence is not an error (docs task scope — must
    # degrade gracefully when ui/styles.qss doesn't exist yet).
    if _STYLES_PATH.is_file():
        app.setStyleSheet(_STYLES_PATH.read_text(encoding="utf-8"))

    engine = TorrentEngine()
    window = MainWindow(engine)
    window.show()

    try:
        return app.exec()
    finally:
        engine.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
