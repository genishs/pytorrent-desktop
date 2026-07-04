"""Tests for the OS-shutdown seam (docs/DECISIONS.md D3, core/system_actions.py).

**Safety-critical test file:** every test here monkeypatches
``subprocess.run`` (and, where relevant, ``platform.system``) so that
:func:`request_system_shutdown` never invokes a real shutdown command on the
machine running the test suite. If a future edit to
``system_actions.py`` calls anything other than the module-level
``subprocess.run``/``platform.system`` seams patched below, these tests would
no longer be guaranteed to intercept it — keep the implementation to that
shape.
"""

from __future__ import annotations

from pytorrent_desktop.core import system_actions


def test_request_system_shutdown_calls_windows_shutdown_command(monkeypatch) -> None:
    monkeypatch.setattr(system_actions.platform, "system", lambda: "Windows")
    calls: list[tuple[tuple, dict]] = []
    monkeypatch.setattr(
        system_actions.subprocess, "run", lambda *a, **k: calls.append((a, k))
    )

    system_actions.request_system_shutdown()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[0] == ["shutdown", "/s", "/t", "0"]
    assert kwargs.get("check") is False


def test_request_system_shutdown_is_a_noop_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(system_actions.platform, "system", lambda: "Linux")
    calls: list[tuple] = []
    monkeypatch.setattr(system_actions.subprocess, "run", lambda *a, **k: calls.append(a))

    system_actions.request_system_shutdown()

    assert calls == []  # must not attempt any command on an unsupported platform


def test_request_system_shutdown_swallows_a_missing_binary(monkeypatch) -> None:
    monkeypatch.setattr(system_actions.platform, "system", lambda: "Windows")

    def _raise(*_a, **_k):
        raise OSError("shutdown.exe not found")

    monkeypatch.setattr(system_actions.subprocess, "run", _raise)

    system_actions.request_system_shutdown()  # must not raise
