---
description: Where am I in the modernization workflow — artifact inventory, staleness, secrets hygiene, next step
argument-hint: <system-dir>
---

<!-- Modified by CapTech on 2026-09-14: corrected where the staleness check looks for the index: `analysis/$1/` holds only in a `legacy/`+`analysis/` workspace, and on a plain checkout the stores fall back to `<repo-root>/legacylift-docs/`, so the check silently skipped rather than comparing. Also adds the SS2 staleness rule comparing the discovery artifacts against the legacylift-search index, so a report derived from a stale index is no longer shown as "nothing stale". -->

Report where the modernization of `$1` stands, in one screen. This is a
read-only command — inspect, never modify.

## 1 — Artifact inventory

Check `analysis/$1/` and `modernized/$1*/` and build a table — one row per
workflow stage, with the artifact's presence and modification time:

| Stage | Artifacts |
|---|---|
| preflight | `PREFLIGHT.md` |
| assess | `ASSESSMENT.md`, `ARCHITECTURE.mmd` |
| map | `topology.json`, `TOPOLOGY.html`, `*.mmd`, `extract_topology.*` |
| extract-rules | `BUSINESS_RULES.md`, `DATA_OBJECTS.md` |
| brief | `MODERNIZATION_BRIEF.md` (note whether the approval block is signed) |
| harden | `SECURITY_FINDINGS.md`, `security_remediation.patch` |
| uplift | `DELTA_CATALOG.md`; `modernized/$1-uplifted/UPLIFT_NOTES.md` (note per-project: builds on target? baseline reproduced?) |
| transform | each `modernized/$1/<module>/` dir — note test presence and whether `TRANSFORMATION_NOTES.md` exists |
| reimagine | `modernized/$1-reimagined/` — note per-service acceptance tests and the `CLAUDE.md` handoff (reimagine's completion markers; it does NOT write `TRANSFORMATION_NOTES.md`) |

## 2 — Staleness

Flag any artifact older than an upstream artifact it derives from:

- `MODERNIZATION_BRIEF.md` older than `ASSESSMENT.md`, `topology.json`,
  or `BUSINESS_RULES.md` → the brief no longer reflects discovery;
  recommend re-running `/modernize-brief`.
- `TOPOLOGY.html` older than `topology.json` → re-run the injection step
  from `/modernize-map`.
- Any `TRANSFORMATION_NOTES.md` older than `BUSINESS_RULES.md` → the
  module may not implement the latest rule set; list which.
- `ASSESSMENT.md` older than the Layer-0 index it quotes → the LOC table,
  domain counts, coverage and extraction-gap figures all predate the
  current index; recommend re-running `/modernize-assess`. The index is
  `<analysis-dir>/index/code-search/index.sqlite`. Resolve `<analysis-dir>`
  the way `legacylift-search` does, and note that it is **not** always
  `analysis/$1/`: that holds only in a `legacy/` + `analysis/` workspace. On
  a plain checkout — `repos/<system>/<unit>`, for instance — the stores fall
  back to `<repo-root>/legacylift-docs/{index/code-search,knowledge}`. Check
  both before concluding an index is absent. **Skip this check entirely when that file does not exist**; an
  absent index means the figures were never index-derived, which is not
  staleness. Also compare against `<analysis-dir>/knowledge/knowledge.sqlite`
  when present: domain tagging lives there and survives an index reset, so
  it can be stale independently of the index.

## 3 — Secrets hygiene

- Does `analysis/.gitignore` exist and cover `SECRETS.local.md` /
  `*.local.patch`? (`git check-ignore` when in a git repo.)
- If `SECRETS.local.md` exists: confirm it is NOT tracked
  (`git ls-files --error-unmatch`, expect failure) and has never been
  committed (`git log --all --oneline -- <path>`, expect empty). If
  either check fails, say so prominently and recommend rotation plus
  history scrubbing.

## 4 — Verdict

End with three lines:
- **Where you are** — the furthest completed stage and roughly how much
  of the system it covers (e.g. "mapped 100%, 2 of 14 modules
  transformed").
- **What's stale** — or "nothing".
- **Next command** — the single most useful next step, with a one-line
  reason.
