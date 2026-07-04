[한국어](CHANGELOG.md) | **English**

# Changelog

All notable changes to pytorrent-desktop are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows the
[roadmap](docs/ROADMAP.en.md) (`0.MINOR.PATCH`, **all core features working at 0.5.0**).

## [Unreleased]

Next milestone: **0.2.0 — GUI**. See the [roadmap](docs/ROADMAP.en.md).

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
