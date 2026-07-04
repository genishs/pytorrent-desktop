[한국어](CHANGELOG.md) | **English**

# Changelog

All notable changes to pytorrent-desktop are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows the
[roadmap](docs/ROADMAP.en.md) (`0.MINOR.PATCH`, **all core features working at 0.5.0**).

## [Unreleased]

Next milestone: **0.5.0 — Core complete & `.exe` packaging**. See the [roadmap](docs/ROADMAP.en.md).

## [0.4.0] - 2026-07-04

**Privacy & automation.** IP hiding (proxy) and on-complete actions.

### Added
- **Privacy** (engine) — `configure_privacy(ProxyConfig | None)`: SOCKS5 + `anonymous_mode` + `proxy_hostnames` + proxied peer/tracker connections; with the kill switch on, DHT/LSD/UPnP/NAT-PMP are disabled so there is no direct-connection fallback (D1). Host/port validation → `ProxyConfigError`. `privacy_status()`, `set_listen_port()`. Proxy state shown in the status bar.
- **Settings persistence** (`core/config.py`) — `ConfigStore` saves/loads `config.json` (%APPDATA%) with default save path, proxy (host/port/user/kill-switch), on-complete action, and port, written atomically (corrupt file falls back to defaults). **The proxy password is not in the schema — memory only** (D2).
- **Settings dialog** (`ui/dialogs.py`) — General / Privacy / On-complete tabs.
- **On-complete action** (D3) — opt-in. When all torrents finish, a **cancellable 30-second countdown** precedes quitting the app or shutting down the system. System shutdown is isolated in a single seam (`core/system_actions.py`), **unreachable without the countdown expiring**, runs on Windows only, and flushes resume data first.
- **Tests** — proxy-settings application, config round-trip (password never persisted), countdown/cancel, and that the shutdown seam is only ever called through a mock. 124 passing total.

### Changed
- `pyproject`/`__init__` version `0.3.0` → `0.4.0`.

### Notes
- **Real kill-switch leak prevention cannot be verified headlessly** — it needs a live proxy + packet capture. The settings combination is unit-tested; real-world verification is a manual step (noted in code/docstrings).
- I2P anonymous mode (post-0.5) and `.exe` packaging (v0.5) are out of scope.

## [0.3.0] - 2026-07-04

**Persistence & sequential queue.** Session restore across restarts and one-at-a-time downloading.

### Added
- **Session restore** — `ResumeStore` (`core/resume_store.py`): saves/loads `%APPDATA%\pytorrent-desktop\resume\<key>.fastresume` with **atomic writes** (`.tmp` + `os.replace`); unparseable files are quarantined to `resume/bad/`. Loaded on startup to restore the session.
- **`core/config.py`** — `AppPaths` (Windows `%APPDATA%`, XDG fallback elsewhere). `EngineConfig.data_dir` now defaults to the real app-data path.
- **Shutdown resume-flush sequence** (ARCHITECTURE §4.3) — `session.pause()` → `save_resume_data` per handle → alert drain that decrements outstanding on **both** success and failure alerts (prevents the documented hang) → log at timeout. Add-time / periodic (60s, gated by `need_save_resume_data`) / on-finish (`torrent_finished_alert`) saves share the same path. `remove()` also deletes the `.fastresume` (so it can't resurrect on next startup).
- **Sequential single-download queue** — `set_sequential_queue` (active_downloads=1 + auto_managed), `move_in_queue(up/down/top/bottom)`. UI: a "sequential download" toolbar toggle + "move up/down" context-menu actions.
- **Tests** — ResumeStore round-trip/atomicity/quarantine, session restore, the shutdown-drain "decrements on failed alert" regression, queue ordering. 76 passing total.

### Changed
- `pyproject`/`__init__` version `0.2.0` → `0.3.0`.

### Notes
- SOCKS5 proxy/kill switch & shutdown-on-complete (v0.4) and `.exe` packaging (v0.5) are out of scope.

## [0.2.0] - 2026-07-04

**GUI.** The PySide6 desktop UI, wired to the v0.1.0 engine.

### Added
- **Main window** (`ui/main_window.py`) — toolbar (Add▾ [.torrent/magnet], Pause, Resume, Remove), `QTableView` + `TorrentTableModel` (name/size/progress/↓/↑/peers/state), a **1s `QTimer` polling `engine.snapshot()`** (updates in place when unchanged so selection is preserved), a status bar (aggregate ↓/↑ rate, active/total), and a right-click context menu. Engine calls are wrapped in `EngineError` handling → `QMessageBox`.
- **Dialogs** (`ui/dialogs.py`) — `AddTorrentDialog` (.torrent/magnet tabs + save path + "add paused", live validation) and `RemoveDialog` (list-only vs delete-data, list-only default).
- **Entry point** (`__main__.py`) — builds `QApplication`, loads `ui/styles.qss` if present (graceful otherwise), and runs `engine.shutdown()` on exit.
- **Styling** (`ui/styles.qss`) — light-theme QSS covering all widgets. **`docs/DESIGN.md`** (KO/EN) with design tokens and integration notes.
- **pytest-qt UI tests** — `tests/conftest.py` (offscreen) plus model/dialog/main-window tests. Full suite: 53 passing (14 engine + 39 GUI).

### Changed
- `pyproject`/`__init__` version `0.1.0` → `0.2.0`.

### Notes
- "Add paused" is implemented as add-then-`pause()` (the engine's add signature is unchanged).
- Settings dialog / SOCKS5 proxy (v0.4), sequential-queue UI (v0.3), and shutdown-on-complete (v0.4) are out of this milestone's scope.

## [0.1.0] - 2026-07-04

**Engine foundation.** A GUI-independent engine over libtorrent, plus the project
foundation and process needed to reach v0.1.0.

### Added
- **`core.engine.TorrentEngine` implementation** — `EngineConfig`/`ProxyConfig` config objects; the extended `TorrentStatus` (D4: info_hash, name, save_path, sizes, progress, rates, peers/seeds, state, queue position, error — `error` read from `status().errc`); `.torrent`/magnet add with pre-flight validation and duplicate detection (D5 v1/v2/hybrid keying via `info_hashes().get_best()`); pause/resume/remove; `snapshot()`; idempotent `shutdown()`.
- **Typed error hierarchy** `core/errors.py` — `EngineError` base with `InvalidMagnetError`/`TorrentFileError`/`DuplicateTorrentError`/`SavePathError`/`UnknownTorrentError`.
- **14 headless engine tests** (`tests/`) — network-free coverage of create/shutdown, typed errors, duplicate add, extended status shape. (Local: ruff clean, 14 passed.)
- **Design docs**: `docs/ARCHITECTURE.md` (engine API contract, concurrency, shutdown sequence, privacy/kill-switch, sequential queue, search-plugin seam, packaging — verified vs libtorrent 2.0.13), `docs/UX-SPEC.md` (screens, dialogs, state transitions, edge cases, 11 acceptance scenarios, wireframes), `docs/DECISIONS.md` (decision log).
- **GitHub Actions CI** (`.github/workflows/ci.yml`) — Ubuntu + Windows / Python 3.12: ruff + pytest + a libtorrent/engine smoke step.
- **Release process** — `.github/workflows/release.yml` (tag `v*` → GitHub Release from CHANGELOG notes, `0.x` as prerelease), PR template, `docs/PROCESS.md` (branch strategy, PR→CI→merge→tag→release flow), and `main` branch protection (PR required + both CI checks required).
- **Docs internationalization (D7)** — Korean primary (`X.md`) + English (`X.en.md`), with a language-switch link at the top of each.
- `pytest-qt` dev dependency (UI tests land with the v0.2.0 GUI).

### Changed
- `pyproject` version `0.1.0.dev0` → `0.1.0`.
- Default documentation language switched to Korean (English kept as `.en.md`).

### Notes
- Resume-data persistence & sequential queue (v0.3), SOCKS5 proxy/kill switch (v0.4), and the GUI (v0.2) are intentionally left as stubs, with next-milestone hooks documented at the call sites.
- Python 3.14 has no `libtorrent` wheel yet — development pins 3.11–3.13 (uv auto-installs 3.12).

## [0.1.0.dev0] - 2026-07-04

Project bootstrap.

### Added
- Project scaffold: `src/` layout, `pyproject.toml` (hatchling, Python 3.11–3.13 pin, `libtorrent==2.0.13`, PySide6), MIT `LICENSE`.
- `core.engine.TorrentEngine` initial scaffold (facade + TODO stubs).
- `README.md` (with lawful-use notice), `docs/SCOPE.md`, `docs/ROADMAP.md`, this changelog.
- Verified: engine boots on `libtorrent 2.0.13` under a uv-managed Python 3.12 environment (Windows).

### Notes
- Python 3.14 has no `libtorrent` wheel yet — development pins 3.11–3.13.
