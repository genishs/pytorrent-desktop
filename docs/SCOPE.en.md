[한국어](SCOPE.md) | **English**

# Scope

Source of truth for what pytorrent-desktop is (and isn't) building. Owned by
product-lead; refined by product-planner into detailed UX specs.

> **Versioning:** the core/MVP features below are scheduled across releases up to
> **v0.5.0**, where all of them work. See [`ROADMAP.md`](ROADMAP.en.md).

## Product principle

A **general-purpose, lawful** BitTorrent client for Windows. Ships with no
trackers, torrents, or bundled search sites. Any search provider is optional,
user-enabled, and queries third-party services at the user's own responsibility.

## MVP (v0.1) — acceptance criteria

A build is MVP-complete when all of the following pass in a real demo:

1. **Open `.torrent`** → save-path dialog → download starts.
2. **Add magnet** (paste) → metadata fetched → download starts.
3. **Live list** shows name / size / progress % / ↓ & ↑ speed / peers / state,
   refreshing ~every second.
4. **Pause / resume** works per torrent.
5. **Remove** offers "from list only" vs "delete data too".
6. **Sequential single-download queue**: with one-at-a-time enabled, only one
   torrent downloads at a time; the next starts when it finishes.
7. **Session restore**: after restart, in-progress torrents resume (resume data).
8. **Privacy**: configuring a SOCKS5 proxy routes traffic through it with
   `anonymous_mode`; kill switch prevents direct connections if the proxy drops.
9. **On-complete action** (opt-in): quit the app or shut down the system when all
   downloads finish.
10. Runs from a standalone **PyInstaller `.exe`** with no Python/env-var setup.
11. Verified by a real download of a lawful torrent (e.g. Ubuntu ISO) to 100%.

## Out of MVP (post-MVP backlog)

- **Search**: pluggable search-provider architecture; first provider is a
  [btdig](https://btdig.com/)-style DHT/meta-search (query + parse results →
  magnets). User-enabled, behind the legal notice. We do **not** build a DHT
  crawler/indexer, and we do **not** bundle providers targeting piracy sites.
- **Magnet protocol handler** (browser click → app) via the installer.
- **Inno Setup installer**: shortcuts, uninstaller, protocol-handler registration.
- **I2P** anonymous mode.
- **Time-based scheduling** (start at a specific time).
- Per-file selection, speed limits, system tray, seeding-ratio management,
  categories/labels, multi-language.

## Non-goals

- Building a VPN or an anonymity network. Privacy relies on a user-supplied
  proxy/VPN/I2P; the app only routes through it and provides a kill switch.
- Hosting or distributing any copyrighted content.

## Architecture (summary)

- `core/` — libtorrent engine facade (`TorrentEngine`), **no Qt imports**,
  headlessly testable.
- `ui/` — PySide6: main window, `QTableView` model/view, dialogs, settings.
- Concurrency (MVP): libtorrent runs its own threads; the UI polls
  `engine.snapshot()` on a 1s `QTimer`. Post-MVP: move to alert-driven updates.
- Config & resume data under `%APPDATA%\pytorrent-desktop\`.
