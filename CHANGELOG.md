# Changelog

All notable changes to pytorrent-desktop are recorded here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows the
[roadmap](docs/ROADMAP.md) (`0.MINOR.PATCH`, **all core features working at 0.5.0**).

## [Unreleased]

Working toward **0.1.0 — Engine foundation**. See the [roadmap](docs/ROADMAP.md).

### In progress
- `docs/ARCHITECTURE.md` — engine API contract, concurrency & shutdown sequence, resume-data persistence, privacy/kill-switch, queue, packaging (system-architect).
- `docs/UX-SPEC.md` — screen-by-screen UX, dialogs, states, edge cases, acceptance scenarios (product-planner).

## [0.1.0.dev0] - 2026-07-04

Project bootstrap.

### Added
- Project scaffold: `src/` layout, `pyproject.toml` (hatchling, Python 3.11–3.13 pin, `libtorrent==2.0.13`, PySide6), MIT `LICENSE`.
- `core.engine.TorrentEngine` — GUI-independent facade over libtorrent: session setup, add `.torrent`/magnet, pause/resume/remove, 1s status `snapshot()`; sequential-queue and SOCKS5-privacy methods stubbed with TODOs.
- `README.md` (with lawful-use notice), `docs/SCOPE.md` (MVP acceptance criteria + backlog), `docs/ROADMAP.md`, this changelog.
- Verified: engine boots on `libtorrent 2.0.13` under a uv-managed Python 3.12 environment (Windows).

### Notes
- Python 3.14 has no `libtorrent` wheel yet — development pins 3.11–3.13 (uv auto-installs 3.12).
