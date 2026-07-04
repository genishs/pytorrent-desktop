[한국어](ROADMAP.md) | **English**

# Roadmap

**Goal: every core feature works at `v0.5.0`.** Versions before 0.5.0 are
incremental milestones toward that; versions after add non-core capabilities on
top of a stable core.

## Versioning policy

Pre-1.0 semantic-ish versioning `0.MINOR.PATCH`:

- **MINOR** = a feature milestone below (0.1 → 0.5).
- **PATCH** = fixes/polish within a milestone.
- `1.0.0` comes after 0.5 core is stable **and** the first post-core wave
  (search + installer) has shipped and settled.

Every release gets an entry in [`CHANGELOG.md`](../CHANGELOG.en.md).

## Milestones

| Version | Theme | Scope |
|---|---|---|
| **0.1.0** | Engine foundation | `TorrentEngine` over libtorrent: add `.torrent` & magnet, pause/resume/remove, status snapshot. Verified headlessly (CLI smoke test). *(scaffold done; engine impl in progress)* |
| **0.2.0** | GUI | PySide6 main window, torrent table with live (1s) columns, Add dialog, Remove (list-only / delete-data), pause/resume from UI |
| **0.3.0** | Persistence & queue | Resume-data save/load → **session restore** on restart; **sequential single-download queue** (one at a time, then next) |
| **0.4.0** | Privacy & automation | **SOCKS5 proxy + `anonymous_mode` + kill switch**; **on-complete action** (quit app / shut down system, opt-in) |
| **🎯 0.5.0** | **Core complete** | All of the above integrated and stable, shipped as a standalone Windows **`.exe`** (PyInstaller). Verified by a full lawful download end-to-end. **This is the "all core features work" target.** |

## Beyond core (post-0.5.0)

- **Search** — pluggable provider architecture; btdig-style DHT/meta-search provider (user-enabled, behind the legal notice). No DHT crawler, no bundled piracy providers.
- **Installer** — Inno Setup: shortcuts, uninstaller, and `magnet:` protocol-handler registration (browser click → app).
- **I2P** anonymous mode.
- **Time-based scheduling** (start at a specific time).
- Per-file selection, speed limits, system tray, seeding-ratio management, categories/labels, multi-language.
- `1.0.0` — stable core + first post-core wave.

## Feature → version index

| Feature | Lands in |
|---|---|
| Open `.torrent` / add magnet | 0.1 (engine) → 0.2 (UI) |
| Live torrent list | 0.2 |
| Pause / resume / remove | 0.2 |
| Sequential single-download queue | 0.3 |
| Session restore (resume data) | 0.3 |
| Privacy: SOCKS5 + kill switch | 0.4 |
| On-complete: quit app / shutdown | 0.4 |
| Windows `.exe` packaging | 0.5 |
| Search (btdig-style) | post-0.5 |
| Magnet protocol handler + installer | post-0.5 |
