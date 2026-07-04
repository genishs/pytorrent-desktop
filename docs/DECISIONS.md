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

## Queued for the owner (revisit on return, non-blocking)
- Whether the kill switch should offer an "anonymous DHT over proxy (UDP-associate)"
  advanced mode vs the safe tracker+PEX default (D1). Default ships; toggle is a
  post-MVP enhancement.
- Whether to persist the proxy password (D2) — needs a "remember password" UX call.
