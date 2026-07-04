"""Shared pytest fixtures/setup for the whole test suite.

Must run before PySide6 is imported anywhere, so the Qt platform plugin is
forced to the headless ``offscreen`` backend for CI/dev boxes without a
display (docs/ARCHITECTURE.md's GUI tests use pytest-qt's ``qtbot``, which
creates a real ``QApplication``).
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
