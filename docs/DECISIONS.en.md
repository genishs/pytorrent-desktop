[한국어](DECISIONS.md) | **English**

# Decision log

Lightweight ADRs. Each entry: the decision, why, and whether it's reversible.
Decisions marked **(PM default, AFK)** were made autonomously by the PM while the
owner was away, choosing the reversible/safe option; they can be revisited by
product-lead or the owner without penalty.

## D1 — Kill switch = no-leak via `anonymous_mode`, not `force_proxy`
**Decision:** When a SOCKS5 proxy is configured with the kill switch on, correctness
rests on `anonymous_mode=true` + `proxy_hostnames=true` (proxy all peer/tracker/DHT
name lookups) and disabling DHT/LSD/UPnP/NAT-PMP; peer discovery falls back to
tracker + PEX only. `force_proxy` is treated as a deprecated alias, not the guarantee.
**Why:** Architecture verification against libtorrent 2.0.13 showed `force_proxy` is
deprecated; `anonymous_mode` + `proxy_hostnames` is the authoritative no-leak path.
**Reversible:** Yes (settings + a leak-test before shipping v0.4). **(PM default, AFK)**

## D2 — Proxy password stored in memory for MVP
**Decision:** Hold the SOCKS5 password in memory only for MVP; persist via Windows
DPAPI post-MVP if we add "remember".
**Why:** Avoid shipping plaintext secrets; DPAPI integration is not core-critical.
**Reversible:** Yes. **(PM default, AFK)**

## D3 — On-complete action: opt-in, with a cancellable 30s countdown
**Decision:** Default on-complete action is **None**. When the user enables "quit app"
or "shut down system", perform it only after a **30-second cancellable countdown**
dialog. System shutdown never happens without that window.
**Why:** Executing a system shutdown with zero confirmation is unsafe; the countdown
makes a powerful, irreversible-feeling action recoverable. (Raised by product-planner
as OPEN-3.)
**Reversible:** Yes. **(PM default, AFK)**

## D4 — `TorrentStatus` extended to the architecture's finalized shape
**Decision:** `TorrentStatus` carries `info_hash, name, save_path, total_bytes,
downloaded_bytes, progress, download_rate, upload_rate, num_peers, num_seeds, state,
is_paused, is_finished, queue_position, error` (error read from `status().errc`, since
libtorrent 2.0 has no `error` state enum). UI error text derives from `error`.
**Why:** UX spec's error/queued states and the columns need these fields; keeps a
single data model between engine and UI.
**Reversible:** Additive. **(PM default, AFK)**

## D5 — Info-hash keying handles v1/v2/hybrid
**Decision:** Key handles/resume files by the torrent's info-hash using libtorrent 2.0
`info_hashes` (v1/v2/hybrid aware), not a bare v1 hash.
**Why:** Correctness for v2 and hybrid torrents; avoids collisions/missed resume.
**Reversible:** Internal. **(PM default, AFK)**

## D6 — UI tests use pytest-qt (Playwright does not apply to a Qt desktop app)
**Decision:** Automated UI tests for the PySide6 GUI use **pytest-qt** (`QtBot`:
simulate clicks/keys, assert on widgets & signals), run headlessly in CI via
`QT_QPA_PLATFORM=offscreen` (plus xvfb on Linux). Playwright/Selenium automate web
browsers and cannot drive native Qt widgets, so they do not apply unless a web UI is
added. Windows-level end-to-end automation of the real window via **pywinauto** is a
post-MVP option. UI tests land with the GUI (v0.2.0).
**Why:** The app is a native Qt desktop GUI, not web; pytest-qt is the standard
in-process, CI-friendly tool. (Owner asked for "Playwright 등" — the intent, automated
UI testing, is honored with the correct tool.)
**Reversible:** Yes. **(PM default, AFK — flag:** if you specifically want Playwright,
that implies a web-UI pivot, i.e. a direction change I did **not** make for you.)

## D7 — Docs language: Korean primary, English as multilingual secondary
**Decision:** Documents and user-facing messages default to **Korean** (`X.md`); an
English version is provided as multilingual support (`X.en.md`). Each file links to its
counterpart at the top. New docs are authored Korean-first. Code identifiers stay
English; commit messages are Korean-first.
**Why:** Owner preference.
**Reversible:** Yes. **(PM default, AFK)**

## D8 — Search is usable only behind an explicit legal-consent gate (experimental)
**Decision:** btdig-style search is off by default, and before use the user must be
informed that (1) using it may be legally problematic, (2) it may **violate the license
of the downloaded software/content**, and (3) **all responsibility is theirs** — and
must explicitly agree via a checkbox + Agree. Until accepted, search and add-to-download
are blocked. Consent is stored in `SearchSettings.consent_accepted` (not re-prompted),
and a legal-notice banner is always shown in the search UI.
**Why:** Search is a legally sensitive experimental feature (owner's directive). Forcing
informed, responsible consent before use makes the risk explicit to the user.
**Reversible:** Yes (gate/settings adjustable). As an experimental feature it lives on develop only.

## Queued for the owner (revisit on return, non-blocking)
- Whether the kill switch should offer an "anonymous DHT over proxy (UDP-associate)"
  advanced mode vs the safe tracker+PEX default (D1). Default ships; toggle is a
  post-MVP enhancement.
- Whether to persist the proxy password (D2) — needs a "remember password" UX call.
