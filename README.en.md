[한국어](README.md) | **English**

# pytorrent-desktop

A Windows desktop **BitTorrent client** built on [libtorrent](https://www.libtorrent.org/) (libtorrent-rasterbar) and [PySide6](https://doc.qt.io/qtforpython/).

> ⚠️ **Legal notice.** This software is a general-purpose BitTorrent client intended **only for downloading and sharing content you are legally permitted to distribute** (e.g. Linux ISOs, Creative Commons media, your own files). It ships with **no trackers, no torrents, and no bundled search sites**. Any optional search provider queries third-party services; you are solely responsible for how you use it and for complying with applicable law and each service's terms.

## Status

🚧 Early development — building toward **v0.5.0, at which all core features work**.
See the [roadmap](docs/ROADMAP.en.md), [changelog](CHANGELOG.en.md), and [scope](docs/SCOPE.en.md).

## Features

### Core features — all working by v0.5.0
- Open a `.torrent` file and download it
- Add a **magnet** link (paste) and download it
- Torrent list with live (1s) **name / size / progress / download & upload speed / peers / state**
- **Pause / resume** per torrent
- **Remove** (from list only, or delete data too)
- **Sequential single-download queue** — download one torrent at a time, then the next (powered by libtorrent's queue: `active_downloads = 1`)
- **Session restore** on restart (resume data)
- **Privacy**: route traffic through a user-supplied **SOCKS5 proxy** with `anonymous_mode` and a **kill switch** (no direct connections if the proxy drops)
- **On-complete action**: quit the app or shut down the system when downloads finish (opt-in)
- Ships as a standalone Windows **`.exe`** (PyInstaller) — no Python or env-var setup for end users

### Beyond core (post-0.5.0)
- **Search**: pluggable search-provider architecture, with a [btdig](https://btdig.com/)-style DHT/meta-search provider (user-enabled, behind the legal notice)
- **Magnet protocol handler** — click a `magnet:` link in the browser to open it here (registered by the installer)
- Inno Setup **installer** (Start Menu shortcut, uninstaller, protocol handler)
- **I2P** anonymous mode
- Time-based **scheduling**
- Per-file selection, speed limits, system tray, seeding-ratio management

## Privacy — how "hide my IP" actually works

This app cannot make you anonymous by itself. It integrates with an **anonymizing service you provide** (a SOCKS5 proxy / VPN's SOCKS5 endpoint, or later I2P) and forces all BitTorrent traffic through it (`anonymous_mode`), with a kill switch that blocks direct connections if the proxy is unavailable. Without a configured proxy, your real IP is visible to peers — as with any torrent client.

## Versioning & roadmap

Pre-1.0 milestones lead to **`v0.5.0`, where every core feature works**:
`0.1` engine → `0.2` GUI → `0.3` persistence & queue → `0.4` privacy & automation →
**`0.5` core complete (Windows `.exe`)**. Full plan in [`docs/ROADMAP.md`](docs/ROADMAP.en.md).

## Development history

Human-readable history is kept in [`CHANGELOG.md`](CHANGELOG.en.md) (Keep a Changelog
format), one entry per release, alongside the git commit history.

## Development

Requires Python **3.11–3.13** (libtorrent has no 3.14 wheel yet). We use [uv](https://docs.astral.sh/uv/).

```bash
uv venv --python 3.12 .venv
uv pip install -e ".[dev]"
uv run pytorrent-desktop
```

## Tech stack

- **Engine**: `libtorrent==2.0.13` (BSD)
- **GUI**: PySide6 (LGPL)
- **Packaging**: PyInstaller → Windows `.exe`
- **Architecture**: `core/` (torrent engine, GUI-independent) ↔ `ui/` (PySide6)

## License

[MIT](LICENSE) © genishs
