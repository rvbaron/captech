# LegacyLift v4 — overview briefing

A single-page engineering briefing on everything that shipped into LegacyLift v4 since `v3.7.0`,
written for a CTO-level reader. Open [`index.html`](./index.html) in any browser — it is
self-contained and needs no server, no build step and no network.

The copy in this repository — [`index.html`](./index.html) — is the authoritative one. There is no
published copy to keep in step with it.

## Contents

| Path | What it is |
|---|---|
| `index.html` | The whole briefing — markup, CSS and inline-SVG diagrams in one file |
| `assets/fonts/fonts.css` | `@font-face` declarations, vendored from Google Fonts |
| `assets/fonts/*.woff2` | Hanken Grotesk and IBM Plex Mono, latin + latin-ext subsets (~164 KB total) |

There are no scripts and no external requests. The six figures — diagrams and charts alike — are
hand-authored inline SVG, themed through CSS custom properties, so they render in both light and
dark themes and scale to phone width.

## Scope of the briefing

Everything released as **`v4.0.0`** on `main`, of which `v3.7.0` is an ancestor:
**285 commits, 2026-04-23 → 2026-09-15.** The briefing was first written on 2026-09-11 from
`feature/reqs-to-data-store` and revised at the release point; the companion release notes are
[`../release-notes/v4.0.0-release-notes.md`](../release-notes/v4.0.0-release-notes.md).

Ten sections: facts at a glance · the v3→v4 foundation shift · the modernization pathways ·
Layer 0 (the code index) · what is actually in scope · capability domains · requirements as data ·
the review surface · the research basis · in flight and known gaps.

## Provenance of the figures

Every number was re-measured in this repository at the release point on 2026-09-15 — nothing is
estimated. The two kinds of figure, and how to re-derive them:

**Repository measurements.** Line counts via `cloc` over `tools/legacylift_search/src`
(16,017 lines of Python across 45 modules); the test count from `pytest` (1,280 tests across 64
modules, full suite green, exit 0); release deltas from `git diff --numstat v3.7.0..HEAD`;
command, table, enum and validator-rule counts read out of the source.

**Reference-corpus measurements.** These come from a real client Java/JSP estate, referred to in
the briefing as the NNG application, and are not reproducible from a clean checkout — the corpus is
not in this repository. They are recorded, with the commands that produced them, in the execution
plans under [`../exec-plans/`](../exec-plans/):

- `active/reqs-to-data-store.md` — the requirements store: corpus size, ingest and merge results,
  the `MEAS-1`/`MEAS-2`/`MEAS-3` figures, per-round rule counts, index coverage
- `active/layer0-extraction-gap-detection.md` — the coverage widening: 19.60% → 0.00% of
  first-party bytes, 1,229 → 1,504 files discovered
- `active/semantic-code-search-graph-index.md` — Layer 0 milestone state
- `completed/domain-enhancements-plan.md` — the eight domain milestones and their acceptance runs
- `pending/reqs-review-ui.md` — the review surface (§08): what Milestone 1 shipped, and the write
  path it does not yet have. `pending/platform-ui-tests.md` owns the zero-tests gap.

Where the briefing states a gap or a caveat, the pending draft that owns it is in
[`../exec-plans/pending/`](../exec-plans/pending/).

## Regenerating the vendored fonts

The CSS was fetched from this URL with a desktop-Chrome `User-Agent` (so that Google serves
`woff2`), then filtered to the `latin` and `latin-ext` subsets and rewritten to relative paths:

```
https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap
```

Both families are under the SIL Open Font License. Gibson, CapTech's own typeface, has no web
licence available here; Hanken Grotesk is a humanist sans standing in for it. The palette *is* the
CapTech brand system — CapTech Blue `#005eb8`, Dark Blue `#003865`, Yellow `#fdda24` used only as
rule lines, Sky Blue `#00a5df` — over blue-biased neutrals.

## Updating it

Edit [`index.html`](./index.html) directly and commit it — that file is the briefing. Re-measure any
figure you touch rather than carrying it forward, and update the measurement date in §01 and the
footer when you do.
