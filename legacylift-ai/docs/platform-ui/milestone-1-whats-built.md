# platform-ui Milestone 1 — what's built

Built 2026-09-11 on `feature/reqs-to-data-store`, commit `cdbed497`.

`platform-ui/` — Angular 21 + Material front-end, .NET 10 minimal API, read-only
over a copy of NNG's `knowledge.sqlite`. All ten pages render with zero console
errors. Cold start works from plain `dotnet run` + `npm start`, proxy included:
the web app serves on <http://localhost:4200> and proxies `/api` to the API on
port 5189.

For how to run it, the dataset layout and the stack rationale, see
[`platform-ui/README.md`](../../platform-ui/README.md). For the fifteen interview
decisions that shaped it, see the *Decisions of record* section of
[`docs/exec-plans/pending/reqs-review-ui.md`](../exec-plans/pending/reqs-review-ui.md).

## Pages

| Page | State |
|---|---|
| Projects dashboard, project overview | 379 rules, 44 blocked, 148 candidates, 0% SME progress, 3 extraction runs, workflow tracker |
| Requirements list | server-side paging, FTS5 search, 5 facet filters, 6 sort orders |
| Requirement detail | every `gr` column, findings highlighted by span, 383 citations with syntax-highlighted cited code, scenarios, edge cases, merge candidates |
| Review queue | 148 pairs, tabbed by reason with an explanation of each |
| Assessment / Preflight | rendered markdown |
| Graph / Map | 4 `.mmd` diagrams brand-themed + `TOPOLOGY.html` in a frame; 12 domains with file counts |
| Data objects / Business rules | stale June copies, banner-flagged |
| Recommendation | honest empty state — `/modernize-brief` has never been run |
| Requirement formats | the ten SPEC-1 patterns, live corpus counts, deep-linked from each rule's pattern badge |

## Two things the data corrected

**A `evaluated = 0` finding is not a violation.** 24 of the store's 70 `ERROR`
rows are checks that couldn't run (no template to locate slots). The store's gate
is `severity='ERROR' AND evaluated=1`, so the blocked count is **44 rules, not
45**, and those render as `NOT RUN`. The first pass counted them as errors — that
overstated the blocked corpus by a quarter of its findings, and the same bug made
the detail page say "no blocking findings" on a rule showing five red ERROR rows.

**Only 41 of 287 findings carry a `span`.** Those highlight in place (verified:
`statement[58:68]` → `LineMaster`). The other 246 are statement-wide and are
listed instead.

## Things you should know

- **`customer.ple.nng.db.ETSPii` has no `gr` tables at all** — domain tagging
  only. Its Requirements nav is disabled and the overview says why.
- **`platform-ui/data/` is gitignored in full** (4.5 MB store + client-derived
  markdown + cited code slices). `python platform-ui/tools/prepare_data.py`
  rebuilds it. Checked: no credential material reached the copied slices, and
  `PREFLIGHT.md` redacts the PAT itself.
- **`npm install` needs `--legacy-peer-deps`** — npm 10.9.2's resolver crashes on
  vitest 4's peer graph, which Angular 21 pulls in as its default test runner.
  Documented in the README.
- **No tests.** The Angular scaffold's vitest setup is what triggered that npm
  bug, and M1 had no test scope. Worth adding before the write path.
- The status line of `pending/reqs-review-ui.md` was corrected — it still claimed
  "not designed, not scheduled".
