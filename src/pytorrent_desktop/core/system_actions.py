"""OS-level shutdown seam for the "on-complete" automation (docs/DECISIONS.md D3).

Isolated in its own function — a single, trivially mockable call boundary —
so that:

- production code (``ui/main_window.py``) never constructs a shutdown
  command inline, and
- tests can inject a fake in place of :func:`request_system_shutdown` (or
  monkeypatch ``subprocess.run``/``platform.system`` here) and are
  guaranteed to never trigger a real OS shutdown.

This is only ever meant to be called *after* a cancellable countdown
(docs/ARCHITECTURE.md §4.4, docs/UX-SPEC.md §5.6) and *after*
``TorrentEngine.shutdown()`` has flushed resume data — both of those rules
are enforced by the caller, not here.

No Qt import (``core/`` stays GUI-independent, docs/ARCHITECTURE.md §1).
"""

from __future__ import annotations

import logging
import platform
import subprocess

_log = logging.getLogger(__name__)


def request_system_shutdown() -> None:
    """Ask the OS to power off immediately.

    Windows (the primary target platform): ``shutdown /s /t 0``. Other
    platforms (CI also runs on Ubuntu) are not a packaging target for this
    feature, so this is a best-effort no-op there — logged, not raised,
    since by the time this runs the app is already tearing down and there is
    no sensible way to surface a failure to the user.
    """
    system = platform.system()
    if system != "Windows":
        _log.warning("System shutdown is not implemented on platform %r; skipping.", system)
        return
    try:
        subprocess.run(["shutdown", "/s", "/t", "0"], check=False)
    except OSError as exc:  # pragma: no cover - defensive; e.g. missing binary
        _log.warning("Could not invoke the system shutdown command: %s", exc)
