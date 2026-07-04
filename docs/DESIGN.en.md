[한국어](DESIGN.md) | **English**

# Visual Design & Publishing Spec — pytorrent-desktop v0.2.0

Owner: design-publisher. This document takes the layout/states/copy defined in
[`UX-SPEC.en.md`](UX-SPEC.en.md) as given, and records the actual colors,
typography, spacing, and component styling decisions plus their rationale.
The publishing artifact is a single file,
[`../src/pytorrent_desktop/ui/styles.qss`](../src/pytorrent_desktop/ui/styles.qss);
this document is its companion "why."

**Scope:** visual design + QSS publishing only. `main_window.py`, `models.py`,
`dialogs.py`, `__main__.py`, and `tests/` belong to the developer and were not
touched in this pass. Icons reuse the Unicode glyphs already specified in
UX-SPEC (`▾ ❚❚ ▶ 🗑 ⚙ ● ⚠`) — no external image/icon-font assets.

## 1. Theme choice — light

A single light theme, no dark mode. Rationale:
- Neither SCOPE nor UX-SPEC requires a dark theme, and comparable desktop
  file-transfer utilities (qBittorrent, Transmission) default to light —
  matches user expectations.
- A single theme is easier to verify for contrast, and spares the developer
  from building theme-switching logic within MVP scope.
- Colors themselves are a brand-neutral palette (slate/blue-gray family) so
  that once a real brand color is chosen, only the accent tokens need to be
  swapped.

## 2. Design tokens

### 2.1 Color

All values were checked against [WCAG 2.1](https://www.w3.org/TR/WCAG21/) AA
body-text contrast (4.5:1) on white (`#FFFFFF`) or surface (`#F5F6F8`/
`#F0F1F4`) backgrounds.

| Token | Value | Usage |
|---|---|---|
| `bg-app` | `#F5F6F8` | Window/dialog background |
| `bg-surface` | `#FFFFFF` | Table, cards, dialog body, toolbar |
| `bg-surface-alt` | `#F0F1F4` | Table header, zebra even rows, inactive tab |
| `border` | `#D9DCE3` | Default dividers (table outline, toolbar bottom, inputs) |
| `border-strong` | `#C4C9D2` | Button/input borders |
| `text-primary` | `#1E2430` | Body/heading text (12.9:1 on white) |
| `text-secondary` | `#5C6472` | Secondary text, header labels, hints (5.4:1) |
| `text-disabled` | `#ABB1BC` | Disabled text |
| `accent` | `#2F6FEB` | Emphasis — active/downloading state, primary buttons, focus ring, selection |
| `accent-hover` | `#2560D6` | Accent hover |
| `accent-pressed` | `#1E4FB8` | Accent pressed |
| `accent-tint` | `#EAF1FE` | Accent-tinted background (selected row, info banner) |
| `success` | `#1E9E5C` | Finished/seeding progress & state |
| `danger` | `#D6423F` | Error state, destructive buttons, failed input validation |
| `danger-tint` | `#FDEBEA` | Error background |
| `warning` | `#B8790A` | Kill-switch warning, proxy disconnected |
| `warning-tint` | `#FFF4E0` | Warning banner background |
| `neutral` | `#9AA1AC` | Queued/paused/checking — neutral (grayscale) progress bar |

**Semantic mapping rationale** (concretizing UX-SPEC §1.3/§5.1's "meaning
only" instruction): active/downloading = `accent` (blue family — "something
is happening now"), queued/paused/checking = `neutral` (grayscale — visually
communicates "nothing is happening right now"), finished/seeding = `success`
(green — goal reached), error = `danger` (red — must be noticed immediately).
The error state keeps the progress fill gray but wraps the bar in a **red
border only**, expressing UX-SPEC's dual intent (keep last-known progress +
flag an error) in a single widget.

### 2.2 Typography

- Typeface: `Segoe UI` (Windows default), falling back to `Malgun Gothic` for
  Korean text. No embedded fonts — avoids font licensing/size overhead for the
  standalone `.exe` distribution (SCOPE #10); relies solely on OS-bundled
  fonts.
- Size scale (in `pt` — Windows point-size composes naturally with system DPI
  scaling): body/default `9pt`, table header/hints/status bar/badges `8pt`,
  dialog titles `11pt` bold, settings-dialog section labels (e.g. "General",
  "Download") `8pt` bold.

### 2.3 Spacing & shape

| Token | Value |
|---|---|
| `space-xs` | 4px |
| `space-sm` | 8px |
| `space-md` | 12px |
| `space-lg` | 16px |
| `space-xl` | 24px |
| `radius-sm` | 4px (badges, progress-bar chunk) |
| `radius-md` | 6px (buttons, inputs, table, dialog cards, banners) |
| Table row | gridlines `#E4E6EB`, zebra striping (`alternate-background-color`) — improves row tracking in a dense 7-column table (guards against UX-SPEC §6's "tens to hundreds of torrents" case) |
| Progress-bar height | fixed `16px` — thin enough not to bloat row height, thick enough to keep the overlaid `62%` text legible |

## 3. Component-level decisions

### 3.1 Toolbar (`QToolBar`/`QToolButton`)

Flat buttons that only show background/border on hover — with five buttons
always framed, the toolbar reads as visually heavy, and the text+glyph labels
(`❚❚ Pause`, etc.) already carry enough information that background color is
reserved purely as interaction feedback. A disabled button (e.g. "Delete"
with no selection) is dimmed to `text-disabled` only, keeping the background
transparent — expressing "present but not available right now."

### 3.2 Table (`QTableView`/`QHeaderView`)

- The header uses a `bg-surface-alt` background with `text-secondary` text to
  separate it clearly from body rows, with right padding reserved so the sort
  arrow never overlaps the label (UX-SPEC §1.3 MUST: sortable columns with a
  direction arrow). The arrow glyph itself is Qt's native rendering — no
  custom image asset added.
- Selected rows use an `accent-tint` (`#DCE9FD`); a selection that has lost
  focus (`:!active`) is shown in a paler neutral tone, distinguishing "still
  selected" from "currently focused" — avoids the confusing impression that a
  selection vanished after closing a dialog.
- Hover highlighting cannot be driven by QSS alone — the developer must call
  `setMouseTracking(True)` on the view so `QTableView::item:hover` updates on
  every pointer move (not just while a button is held). Documented in the QSS
  header comment.

### 3.3 Progress cell (`QProgressBar`)

The requirement to overlay percentage text on the bar (UX-SPEC §1.3) must be
set **in code** via `QProgressBar.setFormat("%p%")` +
`setAlignment(Qt.AlignmentFlag.AlignCenter)` — Qt Style Sheets do not support
text-alignment properties on `QProgressBar` (not in the official stylable-
widget property list). QSS is only responsible for track/chunk color, border,
and corner radius.

Coloring all seven states (downloading/paused/queued/checking/finished/
seeding/error/fetching-metadata) individually would bloat the palette, so per
UX-SPEC §5.1's instruction they are grouped into **four semantic buckets**
(see §2.1). The dynamic property `rowState`, set by the developer per row, is
the contract documented at the top of the QSS file.

### 3.4 Buttons (`QPushButton`)

Two tiers: a default button (outlined, white) and `variant="primary"` (solid
accent) — every dialog's "Cancel" stays default while the primary action
("Add"/"Save") gets visual priority via `primary`. To match the delete
dialog's label swap to "Permanently delete" once "delete data too" is chosen
(UX-SPEC §3, SHOULD), a separate `variant="danger"` exists — destructive
actions get a distinct color (red) from accent to reduce accidental clicks.

### 3.5 Dialogs (`QDialog`) & tabs (`QTabWidget`)

Since the Add-torrent dialog's two input methods (file path vs. magnet URI)
are already specified as tabs (UX-SPEC §2.1), tabs are styled one tone below
the header (`bg-surface-alt` for inactive, `bg-surface` + bold for active) so
the current input mode is unambiguous.

### 3.6 Inputs / checkboxes / radios & inline validation

- `QLineEdit` has a subtle border by default and switches to an accent border
  on focus — satisfies focus-visibility accessibility criteria.
- Inline errors (invalid magnet, unwritable save path, etc. — UX-SPEC §2.3/
  §4/§6) are contracted as `QLineEdit[state="error"]` (red border+background)
  paired with `QLabel[role="error"]` text underneath. The Add/Save button's
  enabled state is controlled separately by the developer's validation logic
  (`setEnabled(False)`) — QSS only handles the toned-down look of a disabled
  button.

### 3.7 Status bar, banners, toast

The proxy 3-state indicator (§1.4: not configured / connected / disconnected)
maps to three `QLabel[role="proxy-off|ok|warn"]` variants — "not configured"
is neutral gray (explicitly not a warning), "connected" is `success`, and
"disconnected" uses `warning` (amber) rather than `danger`/red — this warning
does not mean immediate data loss; the kill switch is already blocking
traffic, i.e. it's a "safely blocked" state. `danger` is reserved for actual
per-torrent errors so the two severity levels stay visually distinct.

The session-restore-failure banner ("Failed to restore N item(s)", UX-SPEC
§6) and the first-detection proxy-failure toast have no implemented widget
yet, so styling is pre-provisioned as `QFrame[role="banner-warning"]` /
`QFrame[role="toast"]` — the developer only needs to set that property when
building the widget.

## 4. UX-SPEC cross-reference (requirement → publishing coverage)

| UX-SPEC item | QSS coverage |
|---|---|
| §1.3 sort direction arrow (MUST) | `QHeaderView::down-arrow/up-arrow` + header right padding |
| §1.3 progress % overlay | QSS covers color/shape only; alignment/format is code's responsibility (see §3.3) |
| §1.3 state color "meaning only" | §2.1 four-bucket semantic mapping + `rowState` property contract |
| §1.3 empty-list message (SHOULD) | `QLabel[role="empty-state-title/body"]` |
| §1.4 proxy 3-state | `QLabel[role="proxy-ok/off/warn"]` |
| §2.1 tab structure | `QTabWidget::pane`/`QTabBar::tab` |
| §2.3 magnet inline error | `QLineEdit[state="error"]` + `QLabel[role="error"]` |
| §3 delete-dialog radios + destructive button | `QRadioButton` styling + `QPushButton[variant="danger"]` |
| §4 settings section grouping | `QGroupBox`/`QGroupBox::title` |
| §5.1 state-priority coloring (error > paused > …) | `rowState` values cover each state independently; deciding *which* state to show is developer logic, not styling |
| §6 proxy-disconnect / restore-failure banner | `QFrame[role="banner-warning"]` |
| §6 clipboard toast | `QFrame[role="toast"]` |

## 5. Developer integration notes

1. Load the QSS at startup by reading `styles.qss` and passing it to
   `QApplication.setStyleSheet()` — applies to the whole widget tree, no
   further setup required.
2. **Dynamic-property refresh pattern** — Qt does not repaint on
   `setProperty()` alone. After changing a value, call:
   ```python
   widget.setProperty("rowState", "seeding")
   widget.style().unpolish(widget)
   widget.style().polish(widget)
   ```
   (Applies to every widget whose `rowState`/`state`/`role` can change on the
   1-second poll — progress bars, status text, proxy labels, etc.)
3. Enable table-row hover with `table_view.setMouseTracking(True)`.
4. Set the progress-bar percentage overlay in code:
   `QProgressBar.setFormat("%p%")` +
   `setAlignment(Qt.AlignmentFlag.AlignCenter)` at widget construction.
5. If the state-text column (§1.3 "State") needs a colored badge, place a
   `QLabel` as the cell widget and set a property (e.g. `statusKind`) to pick
   one of the §2.1 semantic colors — feel free to append a
   `QLabel[statusKind="..."]` rule at the bottom of the QSS file, reusing the
   §2.1 tokens rather than inventing new colors.
6. Reuse this document's §2 tokens (hex values) verbatim for any new widget —
   don't improvise new colors. Once a real brand palette is set, only the
   four `accent*` tokens need to change to re-tone the whole app.

## 6. Deliverables

- [`src/pytorrent_desktop/ui/styles.qss`](../src/pytorrent_desktop/ui/styles.qss) — the full stylesheet (hardcodes this document's §2 tokens directly; QSS has no variable syntax, so values are repeated with the token name noted in comments)
- This document (`docs/DESIGN.md`, `docs/DESIGN.en.md`)
