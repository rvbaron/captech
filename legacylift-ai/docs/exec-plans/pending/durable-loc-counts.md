# Durable line counts — make LOC a stored fact instead of prose

**Status: DRAFT — not designed, not scheduled.** This file exists so that a measured gap in the
Layer-0 schema is a *declared, deferred* deliverable rather than something each engagement
recomputes with a different tool and a different answer. It was raised while designing
[`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md), which needs a
line count on both sides of its ratio and found there was nowhere to read one from.

This repository's ExecPlan conventions live in [`docs/exec-plan.md`](../../exec-plan.md). This draft is
**not yet a conforming ExecPlan** — no Plan of Work, no Concrete Steps, no acceptance criteria,
because the design conversation has not happened. What it carries is the measurement that motivates
it and the shape the answer has to take.

## The problem, stated as a measurement

**Lines of code are computed at least three times per engagement and stored zero times.**

`/modernize-assess` Step 1 runs `scc legacy/$1` (falling back to `cloc`, then `find`+`wc -l`) and
writes the result into `ASSESSMENT.md` as a rendered table — prose, in a markdown document, with no
machine-readable sibling. `/modernize-preflight` Check 2 only probes `command -v scc` and reports
what degrades without it; it does not run a count. The standalone `cloc` skill can emit JSON to
`legacylift-docs/`, but nothing in the pipeline reads that file.

Nothing persists it. Verified against the schemas (measured 2026-09-01):

- `repo_files` (`store.py:206-215`) carries `size_bytes` and no line count.
- `chunks` (`store.py:219-238`) carries `start_line` / `end_line` per chunk.
- `knowledge.sqlite` has exactly four tables — `domains`, `domain_edges`, `file_domains`,
  `domain_exclusions` — and no LOC in any of them.

So every consumer that wants a line count either shells out to an optional third-party tool or
re-derives one, and the two answers are not the same number.

## What can be derived today, and how well

`MAX(chunks.end_line)` grouped by `file_id` recovers a file's line count without any schema change.
Measured on the existing NNG index (`analysis/customer.ple.nng.app`, 1,229 indexed files):

        exact match to `wc -l`     1,173 / 1,229    95.4%
        mismatched                    56 / 1,229     4.6%   (all undercounts)
        files with zero chunks             0                (fallback chunking guarantees >= 1)

Aggregated for Java it is very close to the external tool: **135,824 lines from the index versus
scc's 135,829 — 0.004% apart.**

Three reasons that is not good enough to leave as the answer:

**It is total lines, not code lines.** scc reports Java as 135,829 lines of which 97,239 are code,
16,250 comment, 22,340 blank. The index has no such split, so an index-derived figure is comparable
to scc's `Lines` column and never to its `Code` column. A consumer that mixes them silently inflates
its own denominator.

**It undercounts, never overcounts.** All 56 mismatches are low. Most are trailing blank lines (2–7
lines); the worst is `ple-persistence/sql/Quartz Clustering Table Creation.sql` at 207 versus a real
337, a 39% undercount, where chunking stopped short of EOF. A statistic whose error is one-sided and
occasionally large is worse than one that is merely approximate.

**`chunks.text` is not a better route.** It is populated for all 15,040 NNG chunks, but chunks do not
cover whole files — `MIN(start_line)` is 18–29 for typical Java, skipping the package and import
block — so counting newlines in stored text is strictly worse than `MAX(end_line)`.

## The shape the answer has to take

**A `line_count` column on `repo_files`, populated at index time.** The cost is close to zero because
the bytes are already in memory: `discover_source_files` (`discovery.py:88-92`) reads each file whole
to compute its SHA-256. Counting newlines in that same buffer adds no I/O and no second walk.

That gives every consumer one number, computed once, with the same provenance as `sha256` and
`size_bytes` — and it stays correct across incremental reindex for free, because it is invalidated by
exactly the same sha comparison that already governs those fields.

## Open questions the design conversation has to settle

**The migration.** `store.py` uses `CREATE TABLE IF NOT EXISTS` migration style, which cannot add a
column to an existing table. Every index in `repos/` would need an `ALTER TABLE repo_files ADD COLUMN
line_count INTEGER` with a null-tolerant read path, or a forced reindex. This makes the plan a
natural first customer of the versioned-migration machinery that
[`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) Milestone 0 is about to build —
sequencing after M0 is probably right, and would validate M0 against a second table.

**Whether the code/comment/blank split is in scope.** It is the split that makes the number
comparable to scc, and it is also a per-language parser problem. Probably out of scope for a first
pass, but the column name should not foreclose it — `line_count` is honest; `loc` is not.

**Whether `stats` surfaces it.** `legacylift-search stats` already prints a file/chunk/symbol table.
A `lines` row is one more query and would let a human sanity-check assess's scc figure against the
index without running either tool twice.

**Whether assess should stop running scc.** Tempting and probably wrong. scc counts files the index
never opens, and its complexity ranking (`scc --by-file -s complexity`) has no equivalent here. The
honest framing is that they answer different questions and the assessment should say which tool
produced which column — not that one replaces the other.

## What must not happen

**Do not present an index-derived line count as scc's `Code` figure.** They differ by roughly 28% on
NNG Java. A consumer comparing one to the other will conclude something false about coverage.

**Do not let this become the gap report's inventory.** `repo_files` contains only files the indexer
agreed to open. A line count stored there can never describe the unindexed side, which is the entire
subject of `layer0-extraction-gap-detection.md`. That plan must count its own lines during its own
walk; this one gives it a consistent denominator, nothing more.

**Do not backfill by re-deriving from chunks.** The 4.6% one-sided error above would be frozen into
the column and become indistinguishable from a measured value. Backfill by reading files, or force a
reindex.

## Prior art in this repository

`repo_files.sha256` and `size_bytes` are the exact precedent: cheap facts captured during the single
read that discovery already performs, invalidated by the same freshness check, and consumed by
several unrelated features. `line_count` belongs in that set and is the odd omission from it.
