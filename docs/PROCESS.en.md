[한국어](PROCESS.md) | **English**

# Development process

Defines how `0.x` milestones flow through branch → PR → CI → tag → release.
Version/feature mapping lives in [`ROADMAP.en.md`](ROADMAP.en.md), the changelog is
[`../CHANGELOG.en.md`](../CHANGELOG.en.md), and the doc-language policy is D7 in
[`DECISIONS.en.md`](DECISIONS.en.md).

## Branching strategy

- **`main`** — always kept releasable. Direct pushes are blocked by branch
  protection; changes land **only via PR**.
- **`release/vX.Y.0`** — the working branch for one milestone. Check
  [`ROADMAP.en.md`](ROADMAP.en.md)'s 0.1–0.5 table for the next milestone and
  branch from `main` with this name (e.g. `release/v0.1.0`).
- **`fix/*`, `docs/*`** — smaller changes outside milestone scope (bug fixes,
  docs-only edits) follow the same flow (PR → CI green → merge) but don't
  necessarily get their own tag/release; they ride along with the next
  milestone release.

## Milestone → PR → merge flow

1. Check [`ROADMAP.en.md`](ROADMAP.en.md) for the next milestone (`vX.Y.0`) and
   its scope.
2. Branch `release/vX.Y.0` off `main` and implement that scope.
3. While working (or right before opening the PR), add a
   `## [X.Y.Z] - YYYY-MM-DD` section to both [`../CHANGELOG.md`](../CHANGELOG.md)
   and [`../CHANGELOG.en.md`](../CHANGELOG.en.md). `release.yml` reads this
   section verbatim to build the release notes.
4. Open a PR to `main`. Fill in the `.github/PULL_REQUEST_TEMPLATE.md`
   checklist (linked acceptance criteria, CHANGELOG updates, tests passing,
   docs kept in sync in both languages).
5. **CI (`.github/workflows/ci.yml`: ubuntu-latest + windows-latest, py3.12,
   ruff + pytest + libtorrent smoke test) must pass before the PR can be
   merged.** This is enforced as a required status check in branch
   protection — a green CI run is the merge gate.
6. Review, then merge (in solo-maintainer stretches, a self-review against the
   checklist stands in for a second reviewer). Prefer **Squash and merge** —
   the milestone branch's many commits collapse into a single clean commit on
   `main`.
7. After merging, tag `main` with `vX.Y.0` and push the tag.
8. The tag push triggers `.github/workflows/release.yml`, which builds a
   GitHub Release from the matching CHANGELOG section.

## Version tagging rules

- Tags use the `vX.Y.Z` form (with the `v` prefix), while `CHANGELOG.md`
  section headers omit it (`X.Y.Z`) — e.g. tag `v0.1.0` matches header
  `## [0.1.0]`. `release.yml` strips the leading `v` from the tag before
  matching, so keep both notations aligned.
- Pre-1.0 versioning follows [`ROADMAP.en.md`](ROADMAP.en.md#versioning-policy):
  MINOR = a roadmap milestone (0.1 → 0.5), PATCH = a fix/tweak within that
  milestone.
- Tags are only ever created on a **merged `main` commit** — never tag a
  `release/*` branch directly.

## Release procedure

1. Before tagging, confirm `main`'s `CHANGELOG.md` and `CHANGELOG.en.md` both
   have the version's section (if missing, `release.yml` falls back to a
   notice saying the section wasn't found).
2. ```
   git checkout main && git pull
   git tag vX.Y.0
   git push origin vX.Y.0
   ```
3. `.github/workflows/release.yml` runs on the tag push, extracts the
   matching `CHANGELOG.md` section, and publishes a GitHub Release via
   `softprops/action-gh-release`. `0.x` versions are marked prerelease;
   `1.0.0` onward are marked as full releases.
4. **Artifact upload (the Windows `.exe`) is not wired up yet** — releases
   today only get notes. Once PyInstaller packaging lands in `v0.5.0`,
   uncomment the build/upload job scaffolded at the bottom of `release.yml`
   to connect it (see the 0.5.0 entry in [`ROADMAP.en.md`](ROADMAP.en.md)).

## Branch protection (`main`)

The following rules are applied as GitHub branch protection on `main`:

- Merges only via PR (no direct pushes).
- Required status checks: both CI jobs, `test (ubuntu-latest, py3.12)` and
  `test (windows-latest, py3.12)`, must pass before merging.
- Applies to admins too, with no bypass (`enforce_admins`).

For the exact command used and its outcome, see the SCM owner's setup record.
To reapply or adjust the rule:

```
gh api --method PUT repos/genishs/pytorrent-desktop/branches/main/protection \
  --input protection.json
```

(`protection.json` lists the two check names above under
`required_status_checks.contexts`, plus `required_pull_request_reviews` and
`enforce_admins: true`.)
