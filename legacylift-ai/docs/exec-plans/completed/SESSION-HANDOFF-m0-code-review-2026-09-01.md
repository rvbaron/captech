# Session Handoff — code review of Milestone 0 (2026-09-01)

> **DISCHARGED 2026-09-01. This file is history; do not work from it.**
> The review it asked for ran (two passes: `/code-review bb148e41..HEAD high` plus a manual pass
> over §5). Seven findings were raised, `CR-01` … `CR-07`, every one reproduced with an executable
> probe. They live in
> [`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md) → `Outcomes & Retrospective` →
> *Milestone 0 code review*, with open checkboxes in `Progress` and the `CR-01` gate written into
> Step 2 and the `migrations.py` interface block. `CR-07` (the 405-vs-408 test count) is closed;
> `CR-01` … `CR-06` are open. Nothing below is stale, but everything actionable in it has moved
> into the plan — that is why this was moved to `completed/`.
>
> Two answers worth keeping in reach, because §5 asked for them specifically: **no plan edit
> weakened a requirement silently** (both narrowings are disclosed and evidenced), and **the
> second-empty-store hazard in §5.5 is closed** — all 13 store-construction sites print their
> resolved directory first.

**Your job:** review the code committed for Milestone 0 of
[`reqs-to-data-store.md`](../active/reqs-to-data-store.md). The work is complete, tested and committed;
nothing is in flight. You are the second reviewer.

**Read §3 before you start.** One adversarial review pass has already run against this diff, its
findings were fixed, and re-reporting them wastes the pass. §3 lists what it found, §4 lists the
properties it verified as correct, and §5 lists what it could **not** check — which is where your
value is highest.

---

## 1. What to review

Four commits on `feature/reqs-to-data-store`. Base is `bb148e41` (last commit before the work):

```
git diff bb148e41..HEAD
```

| Commit | Contents |
|---|---|
| `b31d8cfb` | M0 first half (migration runner) + the path resolver, banner, `--reset` guard |
| `dace7083` | M0 second half: artifact relocation, `.gitignore`, two banner fixes |
| `751c8b26` | Fixes for the first review's three findings |
| `589f5671` | Test-count correction in `CLAUDE.md` only — no code |

1,886 insertions / 68 deletions across 17 files. New files: `migrations.py`, `test_migrations.py`,
`test_reset_guard.py`. The commit messages carry the reasoning and are worth reading first; each
states what was built and why, so this handoff does not repeat them.

**The spec is normative and it is long.** `reqs-to-data-store.md` lines 527-660 (Milestone 0, both
halves) plus its acceptance criteria in `## Validation and Acceptance` (the paragraphs naming
Milestone 0, and the `PR-30` criterion). That text went through nine pre-implementation review
rounds. When code and plan disagree, the plan is presumed right unless the commit says otherwise.

**Do not read** `reqs-to-data-store-additional-info.md` (the 125-finding archive) unless you intend
to propose a change to *how the plan does something* — check there first in that case, because the
reviews may already have rejected it.

---

## 2. Non-obvious context you need

- **The plan file is itself modified by this diff** (46 lines). Some edits are factual corrections,
  some document rules the code introduced. Diff it deliberately:
  `git diff bb148e41..HEAD -- docs/exec-plans/active/reqs-to-data-store.md`. **The highest-value
  thing you can find is a plan edit that weakened a requirement rather than corrected an error.**
  The first reviewer could not run `git` and so could not check this at all (§5).
- **The artifact relocation is invisible in the diff.** `repos/` is gitignored. 353 MB was copied
  from `repos/nng-app-legacylift-analysis/legacy/<system>/legacylift-docs/` into
  `analysis/<system>/`, verified by SHA-256, and the originals then deleted. Verify the *current
  filesystem state* if you want to check it, not the diff.
- **`repos/ctcm/ctcm-api` is the control case.** It has no `legacy/` parent, so it must still
  resolve to `legacylift-docs/` and behave exactly as before. Its `stats` command fails with
  `no such table: symbol_facts` — that is a **pre-existing stale index**, present in the
  pre-change baseline, not a regression. Do not report it.
- **`search` is nondeterministic across processes** (Chroma returns a different neighbour set per
  process). Measured, not inferred: 8 interleaved runs each against the original and the copy gave
  the same ~50/50 split between two rank-1 hits from *both*. Never use `search` output as a
  comparison oracle; `stats` and `domains` are exact.

---

## 3. Already found and FIXED — do not re-report

The first review pass (adversarial, spec-driven) found four issues. Three were fixed in `751c8b26`;
the fourth was recorded in the plan.

| # | Finding | Resolution |
|---|---|---|
| 1 | **The `PR-30` acceptance test was vacuous.** `run_migrations` returns early when nothing is pending, *before* touching `isolation_level`. On a fresh DB the stamp has already written the highest version, so three tests claiming to prove the scoped save/restore never entered the block. | Fixed with `_reopen_with_a_pending_migration` in `test_migrations.py`: create the DB, patch a higher-versioned fixture migration into the list the store reads, reopen. Each test now asserts the fixture migration actually ran. **Verified by injecting the defect** — restore only on the failure path instead of in `finally` — all three fail, then pass on revert. |
| 2 | **`--analysis-dir` did not override "the whole question".** The non-default-relative-`index_dir` branch ran first, so a manifest with `"index_dir": ".legacylift"` plus `--analysis-dir D:\out` wrote the index inside the client checkout while the knowledge store obeyed the override. | Explicit override now wins; with no override the non-default setting still wins (the existing-manifest regression guard). Both halves have tests in `test_config.py`. Precedence now documented in the plan. |
| 3 | **`--analysis-dir` named two different directories** depending on the command — `cli.py` stored the raw string (read as repo_root-relative), `cli_helpers` stored a CWD-resolved absolute path. | Flag now resolves against CWD everywhere; a relative value in the *manifest* still resolves against `repo_root`. Split documented in the plan. Test in `test_cli_smoke.py`. |
| 4 | **M0's second half was checked off while one acceptance criterion was not executed** — the full-`index`-run assertion (no `legacylift-docs/` under the checkout after a real index run), which costs a re-embed of 15,040 chunks through Bedrock. | Substituted with a source-level check (`grep -rn "legacylift-docs" src/` — every hit is help text, a docstring, a manifest default that flows through the resolver, or the guard). An explicit **open sub-checkbox** now sits under the parent in `Progress`, to be discharged by M1's end-to-end run. |

Also fixed during implementation, before that review: a **pre-existing bug in
`_validate_reset_path`** — the user-home refusal never fired, because its own `ValueError` was
raised inside a `try` whose `except Exception: pass` swallowed it. Home was still refused, but by
the directory-name clause under a misleading message. And **two banner defects** found by reading
real output: rich wrapped every path at the 80-column pipe width, and it parsed the literal
`[legacylift-search]` prefix as style markup and silently dropped it.

---

## 4. Verified correct by the first pass — deprioritize

Confirmed present and right; re-checking is cheap but reporting them is noise:

`isolation_level` scoped and restored, nothing set in either `_connect`; per-migration
`BEGIN IMMEDIATE`/`ROLLBACK`/`COMMIT` rather than one transaction around the run; the
emptiness snapshot taken before any `CREATE TABLE` in both stores (`store.py:193`,
`knowledge_store.py:70`); WAL and `foreign_keys` still outside every transaction; both migration
lists shipping the version-1 baseline; every fresh-database version assertion computed via
`highest_version(...)` with no literal; the `--reset` guard keeping all five prior checks plus its
two new clauses; the banner routed exclusively through `Console(stderr=True)` with `--json` stdout
proven parseable; `.gitignore` ignoring `knowledge/knowledge.sqlite*` and `knowledge/chroma/` by
name and never the `knowledge/` directory (a tracked `requirements.jsonl` must live there in M1);
`ctcm-api` still resolving to `legacylift-docs/`; no import cycle from `indexer.py` importing
`cli_helpers`.

---

## 5. Where your value is highest — not yet reviewed

1. **The plan diff.** The first reviewer had no `git` and judged the plan only at HEAD. Nobody has
   compared plan-before against plan-after. See §2, first bullet.
2. **The `751c8b26` fixes themselves.** They are unreviewed by anyone but their author. In
   particular: does `_reopen_with_a_pending_migration`'s `monkeypatch.setattr` on the *store
   module's* bound name actually cover every path the store reads that list through? And does the
   new `explicit_analysis_dir` clause interact correctly with an *absolute* `index_dir` (branch 1,
   which still short-circuits first)?
3. **`cli.py`'s 182 changed lines.** The largest single-file diff, largely repetitive
   flag plumbing across 10 commands. Repetitive diffs are where a single transposed argument hides.
   `--analysis-dir` was added only where `--index-dir` already existed.
4. **Vacuous tests generally.** One was already found. `test_migrations.py` and
   `test_reset_guard.py` are 783 new lines written specifically to catch subtle regressions; a
   second vacuous one is plausible. The technique that worked: inject the defect the test names and
   confirm the test fails.
5. **Second-empty-store risk.** The stated reason the banner exists is that a mis-detected path
   silently creates a second empty store beside a populated one. Is any resolution path still able
   to do that without printing?

---

## 6. Known gaps, deliberately not addressed

Report these only if you disagree with the call, not as new findings:

- `tag-domains`, `domains` and `render-architecture` take no `--analysis-dir`. They do not offer
  `--index-dir` either, so the existing asymmetry was matched rather than widened. The manifest key
  works for them. `domains` being half the relocation-verification oracle is the argument for
  closing it.
- The `vector_store.__init__` first-parameter rename (`index_dir` → root-neutral). Tagged
  "(Milestone 0)" at plan line ~1587 but sitting in Step 5's interface block with no M0 acceptance
  criterion. Left for Step 5 rather than done as an untested rename.
- `INDEX_MIGRATIONS`/`KNOWLEDGE_MIGRATIONS` are tuples, and `run_migrations` returns `list[int]`
  where the plan's interface block first said `-> int`. Plan amended to match; no caller uses the
  return value.

---

## 7. Environment — read before running anything

- Work from `tools/legacylift_search`. Use `.venv/Scripts/python.exe`.
  **The `legacylift-search` on the system `PATH` is a broken shim** — use
  `.venv/Scripts/legacylift-search.exe` or `python.exe -m legacylift_search.cli`.
- Full suite: **408 passing, exit 0**, ~7 minutes (was 357 before M0). Under 408 is a regression
  you caused. Run it in the background.
- ChromaDB must stay pinned at **1.5.9**; a mismatch is a native crash.
- **Do not run a full `index`** against the NNG app to check anything. It re-embeds 15,040 chunks
  through Bedrock — hours plus spend. See §3 finding 4 for the cheap substitute.
- `repos/nng-app-legacylift-analysis/` is gitignored in its entirety, so `git status` stays clean
  no matter what happens there, and nothing under it is recoverable if deleted.
- Pre-change baseline transcripts (`stats`/`domains`/`search` for all three units, captured before
  any code change) are in the previous session's scratchpad under `m0-baseline/`, and the
  post-relocation ones under `m0-verify/`. Session-scoped — if they are gone, the counts are
  reproduced in `dace7083`'s commit message.

---

## 8. Suggested skills

| Skill | Why |
|---|---|
| **`/code-review`** | The primary tool for this task. Target the range explicitly — `/code-review bb148e41..HEAD` — and pass `high` or above: the cheap findings are already gone (§3, §4), so a low-effort pass will likely return empty and tell you nothing. `--comment` and `--fix` are available if you want findings applied. |
| `security-review` | Optional and lower-yield here. Worth it for one narrow reason: `_validate_reset_path` is a destructive-operation guard that had zero tests before this diff and one live bug, and `PRAGMA user_version` is set by string interpolation (safe — an `int` from a hard-coded list — but it reads like an injection defect, and the code says so in a comment). |
| `code-simplifier` | Only if the review turns up genuine duplication. `cli.py`'s repetitive flag plumbing is the candidate. Do not run it speculatively across a 1,886-line diff. |

Do **not** use `/loop`, `Workflow`, or multi-agent orchestration unless the user asks. A single
review pass over a bounded four-commit range does not need fan-out.

---

## 9. Memory pointers

Four memories were written or corrected for this work; read them before forming conclusions about
paths or test counts:

- `m0-relocation-layout` — the new layout, and the two older rules of thumb it **inverts**
- `legacylift-knowledge-store-survives-reset` — **headline now inverted**; read its footer, not
  its title
- `legacylift-venv-aws-extra` — the 408-test baseline
- `reqs-to-data-store-interview` — plan status; M0 shipped, next is M1 Step 1

---

## 10. What happens after this review

Next planned work is **Milestone 1 Step 1**, the shared identity module `identity.py`
(`reqs-to-data-store.md` lines 611-665). It does not depend on this review, but a finding that
changes `migrations.py`'s contract would reach M1 Step 2, which adds `INDEX_MIGRATIONS` version 2 —
the first real migration, and the first time the runner does anything on an existing database.
