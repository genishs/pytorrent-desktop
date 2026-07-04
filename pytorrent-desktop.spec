# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for pytorrent-desktop (Windows).

Committed on purpose (see .gitignore's `!pytorrent-desktop.spec` exception) so
CI and local builds share one definition instead of regenerating flags by hand.

Packaging shape: **one-folder** (`COLLECT`, not `--onefile`). This follows the
explicit decision in docs/ARCHITECTURE.md §10.1:
  - Faster startup — no self-extraction to %TEMP% on every launch.
  - The native `libtorrent` `.pyd` and the PySide6/Qt platform plugin
    (`platforms/qwindows.dll`) end up as plain files in `dist/pytorrent-desktop/`,
    which is the easiest layout to smoke-test and debug when a native
    dependency fails to load on a clean machine.
  - Lower antivirus false-positive rate than a self-extracting single exe.
  - It's the stable base for the post-MVP Inno Setup installer (§10.3):
    Inno Setup consumes a one-folder dist directory as-is.
A single-file "portable" build is *not* produced here; §10.1 treats it as an
optional convenience for later, not the primary release artifact.

Build with:
    pyinstaller pytorrent-desktop.spec

Output: dist/pytorrent-desktop/pytorrent-desktop.exe (+ supporting files in
the same folder). CI zips the whole `dist/pytorrent-desktop/` folder before
attaching it to a release (see .github/workflows/release.yml).
"""

from PyInstaller.building.api import COLLECT, EXE, PYZ
from PyInstaller.building.build_main import Analysis

APP_NAME = "pytorrent-desktop"
ENTRY_POINT = "src/pytorrent_desktop/__main__.py"

# docs/ARCHITECTURE.md task scope: ui/styles.qss must be bundled as a data
# file so `_STYLES_PATH.is_file()` in __main__.py finds it at runtime and the
# app doesn't silently fall back to an unstyled window.
datas = [
    ("src/pytorrent_desktop/ui/styles.qss", "pytorrent_desktop/ui"),
]

# libtorrent is a compiled extension module (`libtorrent/__init__.cp312-*.pyd`)
# imported via a plain `import libtorrent`; PyInstaller's modulegraph picks up
# the extension and its adjacent runtime DLLs automatically through normal
# Analysis. It's still listed as a hidden import as a safety net in case the
# lazy `from pytorrent_desktop.core.engine import ...` inside __main__.main()
# (deliberately wrapped in try/except so a missing native dep gives a clear
# error instead of an import-time crash) hides it from static analysis.
hiddenimports = ["libtorrent"]

a = Analysis(
    [ENTRY_POINT],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # windowed: no console window (this is a GUI app; a background console
    # would sit behind the PySide6 window on every launch).
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
