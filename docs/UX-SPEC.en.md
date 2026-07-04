[한국어](UX-SPEC.md) | **English**

# UX Spec — pytorrent-desktop (MVP v0.1)

Owner: product-planner. Source of truth for **what** and **why**: [`SCOPE.md`](SCOPE.en.md).
This document concretizes SCOPE's 11 MVP acceptance criteria into screen-level layout,
states, copy, and interactions so design-publisher can build the visuals and developer
can wire the logic without further interpretation.

**Legend used throughout:**
- **MUST** — required to satisfy one of SCOPE's 11 MVP acceptance criteria. Not
  optional; cutting it fails MVP.
- **SHOULD** — reasonable UX completeness the planner added (e.g. tooltips, an
  "open folder" menu item). Safe to defer post-MVP if dev-lead needs to cut scope;
  does not block the 11 criteria.
- **OPEN** — a decision or engine change this spec assumes, flagged back to
  product-lead / dev-lead for confirmation before or during build.

## 0. Data model this spec assumes

The UI has no state of its own — it renders `TorrentEngine.snapshot()`
(`src/pytorrent_desktop/core/engine.py`) once per second. Current `TorrentStatus`
fields: `info_hash, name, total_bytes, progress (0.0-1.0), download_rate,
upload_rate, num_peers, state (str), is_paused (bool)`.

**OPEN-1 (to dev-lead):** this spec's state machine (§5) needs two fields the
current dataclass doesn't expose yet:
- `error_message: str | None` — libtorrent's `torrent_status.error` /
  `errc`. Without it the UI can only show "an error occurred," not why.
- `queue_position: int` (libtorrent already exposes this on `torrent_status`) —
  needed to distinguish "queued, waiting its turn" from "active" when the
  sequential queue is on. Without it, a queued torrent and a stalled active
  torrent are visually indistinguishable.

Both are additive, non-breaking changes to `TorrentStatus`. Flagging now so
developer can add them in the same pass as the queue/error work rather than
retrofitting the table model later.

## 1. Main window

### 1.1 Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  [+ Add ▾]  [❚❚ Pause]  [▶ Resume]  [🗑 Remove]              [⚙ Settings]    │  ← toolbar
├─────────────────────────────────────────────────────────────────────────────┤
│ Name          │ Size    │ Progress      │ ↓Speed   │ ↑Speed   │Peers│ State  │
├───────────────┼─────────┼───────────────┼──────────┼──────────┼────┼─────────┤
│ ubuntu-24.04… │ 5.8 GB  │ [███████ 62%] │ 3.2 MB/s │ 128 KB/s │ 14 │ Downloading│
│ debian-net…   │ 654 MB  │ [██████████]  │    -     │  45 KB/s │  6 │ Seeding    │
│ archlinux-2…  │ 900 MB  │ [░░░░░░░  0%] │    -     │    -     │  0 │ Queued     │
│ old-project…  │ 1.2 GB  │ [███░░░  35%] │    -     │    -     │  0 │ Paused     │
├─────────────────────────────────────────────────────────────────────────────┤
│ Total: ↓ 3.2 MB/s  ↑ 173 KB/s   Active 1/4   Proxy: ● Connected (kill switch on)│ ← status bar
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Toolbar actions

| Button | Action | Enable condition |
|---|---|---|
| **Add ▾** | Dropdown with two items: "Open `.torrent` file…", "Add Magnet link…". Each opens the §2 dialog on a different initial tab. | Always enabled (MUST) |
| **Pause** | Pauses all selected items where `is_paused == False` | Enabled only when at least one selected item is running. Disabled if nothing is selected (MUST) |
| **Resume** | Resumes all selected items where `is_paused == True` | Enabled only when at least one selected item is paused (MUST) |
| **Remove** | Opens the §3 removal-confirmation dialog (targets all selected items) | Enabled when one or more items are selected (MUST) |
| **Settings** | Opens the §4 settings dialog | Always enabled (MUST) |

On multi-select, the Pause/Resume buttons stay enabled even in a "mixed state," and
each applies its action only where it makes sense per item (an already-paused item
is not paused again).

### 1.3 Table column definitions (QTableView)

| Column | Source field | Align | Format | Resize | Sort key |
|---|---|---|---|---|---|
| Name | `name` | left | Full name. Ellipsized (…) if longer than the column width; tooltip shows the full name (SHOULD) | Variable width; absorbs remaining space when the window resizes (stretch) | String (case-insensitive) |
| Size | `total_bytes` | right | Human-readable unit: `< 1 KB` → "B", `< 1 MB` → "KB", `< 1 GB` → "MB", above → "GB" (1 decimal place, e.g. `5.8 GB`) | Fixed width (resizable), min 70px | Byte count |
| Progress | `progress` | center | `%` text overlaid on the progress bar (`62%`). Rounded, no decimals | Fixed width 120px, min 80px | 0.0–1.0 value |
| ↓ Speed | `download_rate` | right | `KB/s` / `MB/s`. Shows "`-`" when `0` (after parsing completes, while seeding, or paused) | Fixed width (resizable) | Integer value |
| ↑ Speed | `upload_rate` | right | Same rule as above | Fixed width (resizable) | Integer value |
| Peers | `num_peers` | center | Integer. Shows "0" when zero (not a dash — kept as a literal number to distinguish from a connection failure) | Fixed width, min 40px | Integer |
| State | `state` + `is_paused` (+ `error_message`, `queue_position` — OPEN-1) | center | Label text mapped in §5. Color/badge is design-publisher's call (meaning only: active = accent color, waiting/paused = neutral, finished/seeding = success color, error = danger color) | Fixed width (resizable), min 90px | State priority from §5 (Error > Downloading > Queued > Paused > Seeding > Finished), ties broken by name (SHOULD; string sort is sufficient for the MVP minimum) |

- Clicking any column header toggles ascending/descending sort, with a sort-direction arrow shown in the header (MUST — part of SCOPE #3's "live list" requirement, essential for list readability).
- Initial sort: ascending by insertion order (order added).
- Column widths are drag-resizable (MUST, provided by QTableView by default). Column widths are saved to `QSettings` and restored on relaunch (SHOULD — not one of SCOPE's 11 criteria but a low-cost improvement).
- Row selection: single click = single selection, `Ctrl`+click = toggle-add, `Shift`+click = range selection (MUST, needed for multi-pause/resume/remove).
- When the list is empty: instead of the table, show the guidance text "No torrents added yet. Open a `.torrent` file or add a Magnet link." + an "Add" shortcut button (SHOULD).

### 1.4 Status bar (bottom)

| Item | Content | Refresh rate |
|---|---|---|
| Total download speed | Sum of `download_rate` across all torrents, same unit format as the column | 1s (MUST — SCOPE #3) |
| Total upload speed | Sum of `upload_rate` across all torrents | 1s |
| Active/total count | "Active `N`/Total `M`" — active = state is downloading/seeding (excludes paused, queued, error) | 1s |
| Proxy status | If SOCKS5 isn't configured in settings: "Proxy: Not configured". If configured and connected: "Proxy: ● Connected". If the proxy connection fails and the kill switch is blocking traffic: "Proxy: ⚠ Disconnected — traffic blocked" (warning color) | Immediately on proxy status change, otherwise 1s polling (MUST — SCOPE #8) |

### 1.5 Right-click context menu (table rows)

Right-clicking a row (or rows) updates the selection to that row (kept if already
selected) and shows the menu below:

```
┌────────────────────────┐
│  Pause                  │  ← enabled only if a running item is selected (MUST)
│  Resume                 │  ← enabled only if a paused item is selected (MUST)
├────────────────────────┤
│  Remove…                │  ← opens the §3 dialog, same behavior as the toolbar Remove (MUST)
├────────────────────────┤
│  Open save folder       │  ← opens save_path in Explorer, shown only for single selection (SHOULD)
│  Info (copy info hash)  │  ← copies info_hash to the clipboard, shown only for single selection (SHOULD)
└────────────────────────┘
```

The context menu's Remove does not create a separate flow — it opens the **same §3
dialog** as the toolbar Remove, so the removal confirmation path stays single,
keeping the "safe default" always in effect.

## 2. Add-torrent dialog

### 2.1 Structure — tabbed

The two input methods (file picker vs. text paste) interact differently enough that
forcing them into one form confuses which one to fill in. **Split into tabs**, with
the save path/options in a shared area below the tabs (persists across tab
switches).

```
┌───────────────────────────────────────────────────┐
│  Add Torrent                                   [x] │
├───────────────────────────────────────────────────┤
│  [ .torrent File ] [ Magnet Link ]   ← tabs        │
│ ┌─────────────────────────────────────────────┐   │
│ │  (tab 1) File path: [______________] [Browse]│   │
│ │  (tab 2) Magnet URI:                          │   │
│ │        [________________________________]   │   │
│ │        [ Paste from clipboard ]              │   │
│ └─────────────────────────────────────────────┘   │
│                                                     │
│  Save path: [ D:\Downloads\pytorrent    ] [Browse] │
│  [ ] Add as paused                                 │
│                                                     │
│                              [ Cancel ]  [ Add ]   │
└───────────────────────────────────────────────────┘
```

### 2.2 Tab 1 — `.torrent` file

- Clicking "Browse" opens the standard Windows open-file dialog, filtered to
  `*.torrent` (MUST — SCOPE #1).
- As soon as a file is picked, the dialog parses it and previews the name (see §6
  for parse failure).
- Typing/pasting the path directly into the text field is also allowed (SHOULD).

### 2.3 Tab 2 — Magnet link

- No multi-line input needed; single-line entry (a long magnet URI scrolls within
  one line).
- If the value doesn't start with `magnet:?xt=urn:btih:`, show an inline error
  below the field: "Not a valid magnet link" (validated live, on focus-out) — the
  "Add" button stays disabled (MUST, tied to SCOPE #2 and the §6 edge cases).
- "Paste from clipboard" button: fills the field if the clipboard content matches a
  magnet URI pattern, otherwise shows a toast "No magnet link found on the
  clipboard" (SHOULD).

### 2.4 Shared area

- **Save path**: defaults to the "default save path" from Settings (§4). If the
  user changes this field, that value becomes the default for the next "Add" call
  **for the current app session only** (reverts to the Settings default on app
  restart). To change the Settings default itself, it must be changed in §4.
  (**OPEN-2**: needs product-lead confirmation on "remember for this session only"
  vs. "persist to settings every time." Proposed default is the former — a one-off
  download to a different folder is common, and this way Settings doesn't get
  polluted.)
- **Add as paused** checkbox: when checked, the added torrent starts immediately
  with `is_paused=True` — useful when the user only wants to fetch metadata now and
  start downloading later (SHOULD; not an explicit SCOPE criterion, but requested
  explicitly in the prompt).
- **Add** button: enabled only when, on tab 1, the file path is a valid existing
  file, or on tab 2, the magnet URI matches a valid pattern. If the save path is
  empty, it's always disabled + shows the hint "Choose a save path."
- **Cancel**: discards input and closes. Closes immediately with no confirmation
  (not a destructive action).

### 2.5 UI representation before magnet metadata arrives

The dialog closes immediately on "Add" click, and a **row is created immediately**
in the main table (so the user doesn't feel like the app "froze"). State before
metadata arrives:

| Column | Shown value |
|---|---|
| Name | `(fetching metadata…)` (same text as the engine's fallback) |
| Size | `-` |
| Progress | Indeterminate bar animation, no `%` text |
| ↓/↑ Speed | `-` |
| Peers | Number of peers found via DHT/tracker (can be ≥ 0 — peer discovery proceeds even without metadata) |
| State | `Fetching metadata` |

Once metadata arrives, the row automatically switches to normal on the next
1-second poll (no separate notification needed, MUST — SCOPE #2).

## 3. Removal confirmation dialog

```
┌───────────────────────────────────────────────────┐
│  Remove Torrent                                [x] │
├───────────────────────────────────────────────────┤
│  Removing 2 selected items:                        │
│    • ubuntu-24.04-desktop-amd64.iso                │
│    • debian-netinst.iso                            │
│                                                     │
│  ( ● ) Remove from list only                       │
│        Downloaded files remain on disk.            │
│                                                     │
│  ( ○ ) Delete data too                             │
│        ⚠ Files on disk will also be deleted.       │
│           This action cannot be undone.            │
│                                                     │
│                              [ Cancel ]  [ Remove ]│
└───────────────────────────────────────────────────┘
```

- The default-selected radio is **Remove from list only** (safe default, MUST — so
  data isn't lost by mistake).
- Selecting "Delete data too" makes the ⚠ warning text render in a more emphasized
  style, and the "Remove" button label switches to "Delete permanently" when that
  option is selected (SHOULD — so the user re-confirms what they're about to commit
  to the moment they click the button).
- For multi-select removal, the target list is shown as a scrollable list
  (abbreviated as "and N more" beyond 5 items, SHOULD).
- If removal fails mid-way (e.g. a file is locked by another process), the dialog
  stays open and shows an inline error for that item + offers "Retry"/"switch to
  list-only removal" (not MUST-level, detailed in §6; the minimum requirement is
  not to silently swallow the failure and to notify the user).

## 4. Settings dialog

Built as a single scrollable form with no tabs or section dividers (too few MVP
settings to warrant tabs). Changes take effect only after clicking "Save";
proxy/port changes apply immediately without a session restart (libtorrent's
`apply_settings` supports runtime application).

```
┌───────────────────────────────────────────────────┐
│  Settings                                      [x] │
├───────────────────────────────────────────────────┤
│  General                                           │
│  Default save path: [ D:\Downloads\pytorrent ] [Browse]│
│  Listening port:    [ 6881 ]                       │
│                                                     │
│  Downloads                                         │
│  [ ] Sequential single-download queue (one at a time)│
│                                                     │
│  Privacy — SOCKS5 proxy                            │
│  [ ] Use proxy                                     │
│      Host: [______________]  Port: [_____]        │
│      [x] Kill switch (block direct connections if the proxy drops)│
│      Status: ● Connected / ○ Not configured / ⚠ Connection failed │
│                                                     │
│  On-complete action                                │
│  ( ● ) None   ( ○ ) Quit app   ( ○ ) Shut down system│
│                                                     │
│                              [ Cancel ]  [ Save ]  │
└───────────────────────────────────────────────────┘
```

| Item | Detail rules |
|---|---|
| Default save path | First-run default: `%USERPROFILE%\Downloads\pytorrent-desktop` (created if absent). A path that doesn't exist or isn't writable is validated at the moment "Save" is clicked; failure shows inline error "Can't write to this path" + blocks saving (MUST-level validation — connects to the no-write-permission case in §6). |
| Listening port | Validated in range 1024–65535, out-of-range input shows an inline error. Default 6881 (same as the engine default) |
| Sequential single-download queue | Checking it immediately calls `set_sequential_queue(True)` — MUST, SCOPE #6. If several torrents were already downloading concurrently when this is turned on, the next 1-second poll after saving must reflect the queue rule taking effect — only the top queue position remains, the rest switch to "Queued" — visible immediately in the list. |
| Use proxy + host/port | Unchecking "Use proxy" disables (grays out) the host/port/kill-switch fields. When checked, host/port are required — empty disables "Save" + shows inline error. Saving calls `configure_privacy()` (MUST, SCOPE #8) |
| Kill switch | Default is **On** (safe default). Turning it off shows a warning: "If the proxy connection drops, you may connect directly with your real IP." (SHOULD, so the user explicitly acknowledges the risk) |
| Proxy status display | Same 3-state (not configured/connected/connection failed) display as the §1.4 status bar, shown in Settings too (SHOULD) |
| On-complete action | 3-way radio, default "None." Selecting "Quit app" or "Shut down system" shows the notice: "This will run automatically once all downloads finish. A confirmation window that lets you cancel before it runs will be shown." (see §5.6) (MUST, SCOPE #9) |
| Cancel | Discards changes and closes |
| Save | Applies and closes the dialog only if validation passes |

**OPEN-3 (to product-lead):** choosing "Shut down system" is a destructive action
that can affect other applications and unsaved work. This spec proposes, as the
default design in §5.6, a "cancelable countdown confirmation window before it runs"
(so it doesn't shut down immediately even if completion happens while the user is
away — there's a grace period before it fires). SCOPE doesn't specify this
confirmation step, so it needs product-lead sign-off — an alternative that shuts
down immediately with no confirmation window is also possible, but not recommended
due to data-loss risk.

## 5. State transitions

### 5.1 State list and list display

| Internal state (engine `state` / derived) | List display label | Progress bar | Speed display | Peers |
|---|---|---|---|---|
| `downloading_metadata` | Fetching metadata | Indeterminate | `-` / `-` | Peers found |
| `checking_files` / `checking_resume_data` | Checking files | Check progress (%) | `-` / `-` | Previous session's value kept, or 0 |
| `downloading` (not queue-waiting) | Downloading | Measured % | Measured values | Measured value |
| Queue-waiting — `queue_position > 0` and not yet active (needs the **OPEN-1** field) | Queued | Last progress retained | `-` / `-` | 0 |
| `finished` | Finished | 100% | `-` / measured upload (residual transfer possible even without seeding) | Measured value |
| `seeding` | Seeding | 100% | `-` / measured value | Measured value |
| `is_paused == True` (overrides every other state) | Paused | Last progress retained (grayed) | `-` / `-` | 0 or last value retained |
| Error (needs the **OPEN-1** `error_message` field) | Error | Last progress retained (red border) | `-` / `-` | 0 |

`is_paused` overrides every other displayed state — e.g. pausing a seeding torrent
shows "Paused," not "Seeding." However, error takes priority over paused (a torrent
with an error shows "Error" regardless of its paused state — so the user doesn't
miss the problem).

**State display priority (evaluation order):** Error > Paused > (Fetching metadata >
Checking files > Queued > Downloading > Finished > Seeding)

### 5.2 Normal flow (`.torrent` file, SCOPE #1)

File pick → confirm save path → `Checking files` (only if existing data is
present; can be skipped for new data) → `Downloading` → `Finished` → (if seeds
remain and auto-seeding is on) `Seeding`

### 5.3 Normal flow (magnet, SCOPE #2)

Paste magnet → `Fetching metadata` (§2.5 placeholder row) → name/size finalized
once metadata arrives → `Downloading` → `Finished` → `Seeding`

### 5.4 Pause/Resume (SCOPE #4)

From any state, clicking "Pause" → shows `Paused` within the next 1-second poll,
speed shows 0. Clicking "Resume" → returns to the pre-pause state (resumes
downloading, or seeding if it was already finished).

### 5.5 Queue (SCOPE #6)

With "Sequential single-download queue" On in Settings, and 3 torrents waiting to
download:
1. Only queue position 0 (added first / highest priority) is `Downloading`; the
   other 2 show `Queued`.
2. When position 0 `Finishes`, position 1 automatically switches to `Downloading`
   within the next 1-second poll.
3. Manually "resuming" a queued item or raising its priority is out of MVP scope
   (post-MVP: queue-reorder UI). In MVP, order always follows insertion order.

### 5.6 Running the on-complete action (SCOPE #9)

With "Quit app" or "Shut down system" selected in Settings, the moment **all**
torrents reach `Finished` or `Seeding` (not triggered if even one is
`Downloading`/`Fetching metadata`/`Queued`):

```
┌───────────────────────────────────────────┐
│  All Downloads Complete                    │
├───────────────────────────────────────────┤
│  System will shut down in 30 seconds.      │
│                                             │
│              [ Cancel Now ]                │
└───────────────────────────────────────────┘
```

- 30-second countdown (default needs product-lead confirmation per OPEN-3);
  clicking "Cancel Now" closes the dialog, and the on-complete action doesn't
  trigger again for this session (unless a new torrent is added that brings it
  back to an unfinished state, and everything finishes again, in which case it
  re-triggers).
- If a new torrent is added mid-countdown, bringing the state out of "all
  finished," the dialog auto-cancels (safe even if the user doesn't click Cancel).
- When the countdown ends: quit the app (`QApplication.quit()`) or shut down the
  system (Windows `shutdown /s /t 0` or the API).

## 6. Edge cases

| Case | Trigger condition | UI behavior |
|---|---|---|
| Duplicate add of the same torrent | The info_hash of the `.torrent`/magnet being added is already in the list | Dialog stays open, inline error: "This torrent is already in the list." No new row created. Since the libtorrent session itself doesn't allow duplicate info_hash registration, the UI pre-checks before calling the engine (MUST) |
| Invalid magnet URI | Doesn't match `magnet:?xt=urn:btih:` pattern, or btih hash length is wrong | Blocked by §2.3's live inline validation on the "Add" button itself — never reaches the engine (MUST) |
| Corrupt / unparseable `.torrent` file | `lt.torrent_info()` parse exception | Parsing is attempted right after file selection (before clicking Add); on failure, an in-dialog error: "Couldn't read this file as a torrent. It may be corrupted." Add button stays disabled (MUST) |
| Disk space exhausted | Write failure mid-download (libtorrent auto-pauses the torrent and sets an error) | That row switches to `Error` state, tooltip/details show "Disk space is low" (`error_message` surfaced verbatim, depends on **OPEN-1**). Other torrents unaffected. Once space is freed and the user manually "Resumes," it proceeds normally (MUST) |
| No write permission on save path | Validation fails at add time (§2.4) or settings-save time (§4) | Add dialog: if the write test on the save path fails when clicking "Add," inline error "No permission to write to this folder," add is canceled (engine not called). Settings dialog: same inline validation, blocks "Save" (MUST) |
| Proxy connection fails with kill switch on | Configured SOCKS5 proxy can't connect | §1.4 status bar and §4 show "⚠ Connection failed — traffic blocked." All torrents' peers/speed stay at 0 (not leaking to a direct connection is the key requirement). One-time toast/banner on first detection: "Downloads paused because the proxy couldn't connect. Check your settings." (MUST — SCOPE #8's kill-switch requirement, distinguishing this from what looks like a "frozen" state) |
| No network at all (offline), regardless of proxy/kill switch | OS network adapter missing/disconnected | All torrents show 0 peers, 0 speed; the app doesn't crash and keeps the normal UI. No separate offline-only dialog is shown (often indistinguishable from other cases, avoiding excessive notification) — the status bar's "Active 0" is enough (MUST: survive without crashing / SHOULD: an offline-specific notice is out of scope) |
| Restart after an abnormal exit, resume data corrupted/inconsistent | Resume data file corrupted/mismatched | The corrupted entry starts as `Checking files` (re-check), returning to normal state once the check completes. If completely unreadable, that torrent alone is excluded from the list with a startup banner: "Failed to restore N item(s)" (MUST — so SCOPE #7's session restoration isn't "all or nothing") |
| User away during the shutdown countdown after completion | See §5.6 | Default action runs (proceeds as scheduled unless canceled) — since "works as intended even while the user is away" is the point of this feature, it must run on timeout (MUST) |
| Very long names / many torrents (tens to hundreds) | Large numbers of files/long names | Name column truncation (§1.3), table uses virtual scrolling (QTableView's built-in support) to render without performance loss. The 1-second poll refresh must not stutter — dev-lead sets the concrete performance target from measurement (SHOULD, exact figures are OPEN) |
| File in use during removal (locked by another process) | OS denies file deletion during "Delete data too" | As specified in §3, not silently ignored — shows inline error + offers retry/switch-to-list-only-removal (MUST) |

## 7. Acceptance test scenarios (SCOPE.md MVP criteria 1–11 → executable QA steps)

Each scenario is written as "user action → expected result" so qa-tester can
execute it directly.

**AC-1. Open a `.torrent` file**
1. Toolbar "Add ▾" → click ".torrent file…" → a file dialog appears.
2. Select a legitimate `.torrent` file (e.g. an Ubuntu ISO torrent) → the §2 add
   dialog opens on that tab, with the save path pre-filled with the default.
3. Confirm save path, click "Add" → the dialog closes and a new row appears
   immediately in the main table.
4. **Expected result**: within a few seconds the state changes to `Downloading`
   and the ↓ speed becomes greater than 0.

**AC-2. Add a magnet link**
1. "Add ▾" → "Add Magnet link…" → paste a valid magnet URI → click "Add".
2. **Expected result**: a `Fetching metadata` row appears immediately in the
   table.
3. Wait a few seconds to a few minutes.
4. **Expected result**: name/size update to real values and the state switches to
   `Downloading`, with ↓ speed greater than 0.

**AC-3. Live list updates**
1. With at least one torrent downloading, observe the table for 10 seconds.
2. **Expected result**: name/size/progress/↓ speed/↑ speed/peers/state values are
   visibly changing at roughly 1-second intervals (progress % increasing, speed
   values refreshing).

**AC-4. Pause/Resume**
1. Select a downloading torrent → click toolbar "Pause".
2. **Expected result**: state changes to `Paused` and ↓/↑ speed become `-`.
3. Select the same item → click "Resume".
4. **Expected result**: state returns to `Downloading` (or `Seeding` if it had
   already finished), and speed becomes greater than 0 again.

**AC-5. Remove (list only vs. with data)**
1. Select a torrent → click "Remove" → in the §3 dialog choose "Remove from list
   only" (keep default) → click "Remove".
2. **Expected result**: the row disappears from the table, and checking the save
   path in Explorer shows the files are still there.
3. Add another torrent → select it → "Remove" → this time choose "Delete data
   too" → click "Remove" (or "Delete permanently").
4. **Expected result**: the row disappears from the table, and checking the save
   path in Explorer shows the file/folder has also been deleted.

**AC-6. Sequential single-download queue**
1. Settings → check "Sequential single-download queue" → Save.
2. Add 3 different torrents back to back.
3. **Expected result**: exactly one item shows `Downloading` at a time in the
   table; the other 2 show `Queued`.
4. Wait until the downloading item becomes `Finished` (or `Seeding`).
5. **Expected result**: within the next 1-second poll, one of the queued items
   automatically switches to `Downloading`.

**AC-7. Session restoration**
1. With an in-progress (not yet finished) torrent present, quit the app
   normally.
2. Relaunch the app.
3. **Expected result**: the torrent that was in the list before quitting
   reappears, and its progress continues from near where it left off (it does
   not restart from scratch).

**AC-8. SOCKS5 proxy + kill switch**
1. Settings → check "Use proxy", enter a valid SOCKS5 host/port, keep kill
   switch checked → Save.
2. **Expected result**: the status bar's proxy indicator becomes "● Connected".
3. Stop the proxy server, or change to an invalid host/port, and save.
4. **Expected result**: the status bar switches to "⚠ Connection failed —
   traffic blocked," and every torrent's peer count drops to 0 (use a network
   monitoring tool to confirm no traffic actually leaves directly without the
   proxy — the core kill-switch verification).

**AC-9. On-complete action (opt-in)**
1. Settings → under "On-complete action" select "Quit app" → Save.
2. Add a single small torrent and wait for it to finish.
3. **Expected result**: immediately upon completion (or once the completion
   condition is met), the §5.6 countdown dialog appears.
4. Take no action and wait for the countdown to end.
5. **Expected result**: the app quits automatically. (The "Shut down system"
   option should also be verified separately, but since an actual shutdown
   affects the test environment, it's fine to confirm only that the countdown
   dialog appears and then abort with "Cancel".)

**AC-10. Standalone `.exe`**
1. On a clean Windows machine (or VM) with no Python installed and no separate
   virtual environment, copy `pytorrent-desktop.exe` (the PyInstaller build).
2. Double-click to run.
3. **Expected result**: the main window appears with no separate install/setup,
   and AC-1 through AC-9 all behave identically.

**AC-11. A real, lawful torrent completes 100%**
1. Add a real, lawful torrent such as an Ubuntu ISO.
2. Wait until it completes (100% progress, state `Finished` or `Seeding`).
3. **Expected result**: the downloaded file's checksum (e.g. SHA256) matches the
   checksum published by the official distributor — verifying data integrity as
   well.

## 8. Wireframes (text/ASCII)

Section-by-section ASCII layouts are already included in §1–§5. A summary index
for seeing them all at a glance:

- Main window: §1.1
- Add-torrent dialog: §2.1
- Removal confirmation dialog: §3
- Settings dialog: §4
- On-complete action countdown dialog: §5.6

design-publisher should use the element placement, spacing, and hierarchy from
the layouts above as the basis for the actual visual design (colors, typography,
icons, spacing tokens). Colors are deliberately left unspecified in this spec
(see the "meaning only" notes in §1.3 and §5.1) — only semantic intent is
conveyed.

## 9. Open questions (need product-lead confirmation)

| No. | Question | This spec's default proposal |
|---|---|---|
| OPEN-1 | Whether `TorrentStatus` needs `error_message` and `queue_position` fields added (for dev-lead) | Add them (§0) |
| OPEN-2 | Whether the add-dialog's "remembered" save path default is session-only or persisted to settings | Session-only (§2.4) |
| OPEN-3 | Whether to include a cancelable countdown confirmation before running the "on-complete action," and the countdown duration (30s proposed) | Include it, 30s (§5.6) |
| OPEN-4 | Whether users can reorder queued items (e.g. via drag) | Out of MVP scope (post-MVP), always fixed to insertion order (§5.5) |
| OPEN-5 | Rendering performance target for large numbers of torrents (hundreds) (e.g. how many before 1-second polling starts to stutter) | Undetermined, dev-lead to set from measurement (§6) |
