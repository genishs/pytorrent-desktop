[한국어](BUILD.md) | **English**

# Build — packaging the Windows `.exe`

Defines how pytorrent-desktop is packaged into a standalone Windows
distribution with PyInstaller. For the packaging architecture (the
one-folder decision and its rationale, what must be bundled, and the future
installer hookup point), see [`ARCHITECTURE.en.md`](ARCHITECTURE.en.md) §10.

## Artifact shape: one-folder

`pytorrent-desktop.spec` produces a **one-folder** (`COLLECT`) build, not a
single `--onefile` exe. Rationale ([`ARCHITECTURE.en.md`](ARCHITECTURE.en.md)
§10.1):

- Faster startup than one-file, which self-extracts to `%TEMP%` on every
  launch.
- The native `libtorrent` extension (`.pyd`) and the PySide6/Qt platform
  plugin (`platforms/qwindows.dll`) end up as plain files under
  `dist/pytorrent-desktop/`, which is the easiest layout to diagnose when
  something is missing on a clean machine.
- Lower antivirus false-positive rate than a self-extracting executable.
- It's a stable base a future Inno Setup installer (§10.3) can consume as-is.

Output: `dist/pytorrent-desktop/pytorrent-desktop.exe` plus supporting files
in the same folder (Python runtime, libtorrent, PySide6/Qt, and
`styles.qss`, all under `_internal/`). For distribution, zip the entire
`dist/pytorrent-desktop/` folder.

## Building locally

```powershell
# 1. Install build-time dependencies (pyinstaller is pyproject.toml's
#    [project.optional-dependencies].build extra)
uv pip install --python .venv/Scripts/python.exe -e ".[build]"

# 2. Build from the committed spec
.venv/Scripts/pyinstaller --noconfirm pytorrent-desktop.spec
```

(Plain `pip install -e ".[build]"` + `pyinstaller pytorrent-desktop.spec`
works the same way without `uv`.)

Result:
```
dist/pytorrent-desktop/
  pytorrent-desktop.exe
  _internal/
    libtorrent/...
    PySide6/plugins/platforms/qwindows.dll  (required Qt platform plugin)
    pytorrent_desktop/ui/styles.qss
    ... (Python runtime + other dependencies)
```

`build/` and `dist/` are regenerated every run, so they're not committed
(`.gitignore`). The hand-written `pytorrent-desktop.spec`, by contrast, *is*
committed (with a `.gitignore` exception) so CI and local builds share one
definition.

### Verifying the build (smoke test)

Because this is a GUI app, a full manual check (does the window render, can
you interact with it) still needs a human. But "does the process start and
reach the event loop instead of crashing immediately" can be verified
headlessly:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
Start-Process dist\pytorrent-desktop\pytorrent-desktop.exe
# Still running a few seconds later means libtorrent loaded, Qt
# initialized, and styles.qss was found successfully.
```

Both CI build workflows run this smoke test automatically.

## Building in CI/CD

### PR build guard — `.github/workflows/build.yml`

On PRs to `main` and manual runs (`workflow_dispatch`), a windows-latest
runner builds from `pytorrent-desktop.spec`, runs the headless smoke test,
and uploads the result as a **workflow artifact**
(`pytorrent-desktop-windows`, 14-day retention). No GitHub Release is
created — the point is to catch packaging regressions (e.g. a new
dependency that isn't reflected in the spec, breaking the `.exe`) before a
tag is ever cut.

### Release build — `.github/workflows/release.yml`

On a `v*` tag push:
1. The `release` job extracts release notes from `CHANGELOG.md` and creates
   the GitHub Release (unchanged existing behavior).
2. The `build-windows-exe` job (depends on `release`) builds on
   windows-latest from `pytorrent-desktop.spec`, runs the smoke test, zips
   `dist/pytorrent-desktop/` into `pytorrent-desktop-<tag>-windows.zip`, and
   uploads it as an asset on that release.

Both workflows use `pyinstaller>=6.6` (the `build` extra in
`pyproject.toml`) and Python 3.12 — per
[`ARCHITECTURE.en.md`](ARCHITECTURE.en.md) §1, packaging must target
3.12/3.13 due to libtorrent wheel availability.

## Not done yet

- Code signing: none (no self-signed certificate either). Distribution may
  trigger a SmartScreen warning — a post-MVP concern.
- Inno Setup installer, magnet protocol handler registration: not yet
  built. [`ARCHITECTURE.en.md`](ARCHITECTURE.en.md) §10.3 documents the
  hookup point.
- A one-file "portable" build: only the one-folder artifact is produced
  today. §10.1 mentions one-file only as an optional convenience, and it's
  out of scope for this automation.
