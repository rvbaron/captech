# Session Handoff — rewrite the extraction-gap draft into a conforming ExecPlan (2026-09-01)

> **DISCHARGED 2026-09-01. This file is history; do not work from it.**
> The rewrite happened. The plan is now
> [`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md) — a
> conforming ExecPlan with a Plan of Work, Concrete Steps and acceptance criteria for M0–M4 pinned
> against **both** corpora. The `CLAUDE.md` row is a pointer per the new convention, and the decision
> record stays in `pending/` as the audit trail with its §6 marked done. **The live next action is
> M0, and it is stated in the plan.**
>
> Four things this session established that the plan carries and this file does not:
> both corpora were re-measured with the committed probe and reproduce exactly; two rounded KB values
> in the record's §3.I are stale (`gap` 805 not 804, `asset` 1345 not 1344, which is why that column
> failed its own sum-to-total rule); three questions the record left open were resolved in the plan's
> `Decision Log` (where an own-identity token comes from, where the two authored glob lists are read
> from, how the raw headline is defined); and M0 was de-risked ahead of implementation by fetching
> both upstream linguist files and verifying every resolution the plan pins.
>
> Two things below are still worth reading and are **not** discharged: §5's list of easy-to-get-wrong
> facts (all of which are now also in the plan), and §7's branch state — the merge note in
> `completed/SESSION-HANDOFF-gap-detection-decision-review-2026-09-01.md` §10 still applies, and this
> session added `CLAUDE.md` and `pending/` edits to the same branch.
>
> One correction to §3 below: the test-suite baseline was measured this session. See §7's addendum.

**Your job:** turn [`pending/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md)
— still in its pre-interview draft form — into a conforming ExecPlan, sourced from
[`pending/layer0-extraction-gap-detection-decision.md`](../pending/layer0-extraction-gap-detection-decision.md).

**The design is settled and the numbers are measured. Do not re-open either.** Twenty-seven decisions,
two reference corpora, no open blockers. The record's §6 *Next action* is your specification; this
handoff carries what is not in the record — where things live, what is not committed, and what will
bite you.

Conventions for both this document and the plan you are writing are in
[`docs/exec-plan.md`](../../exec-plan.md) — see *Session handoffs* and *The `CLAUDE.md` plan index*,
both added 2026-09-01. Read them; they are short and they exist because their absence caused the
problems recorded below.

---

## 1. What to do

Record §6 states it: replace the draft's *"The problem, stated as a measurement"* with the record's §2
**and §2b**, delete the `.gitignore` sentence, re-attribute the cause to `include_globs`, convert
*"Open questions"* into the settled design, and add a Plan of Work, Concrete Steps and acceptance
criteria for M0–M4, **pinning both corpora**.

The record's §3.I carries the acceptance numbers. Copy them; do not re-derive them by reading prose.

Milestones, from §3.I:

| | |
|---|---|
| **M0** | Vendor `profiles/linguist.json` + refresh script + pinned-resolution test. Pure data, no CLI. |
| **M1** | The walk: five-tier partition, two-axis exclusion, line counting. Store-free, unit-testable. |
| **M2** | `gaps` command: check one, rich table, `--json`, headline, both modes. |
| **M3** | Check two (`LEFT JOIN symbols`, `--min-bytes`) and the referenced-content reference count. |
| **M4** | `**/legacylift-docs/**` into the manifest defaults + `modernize-assess.md` wiring. |

When you are done, this handoff moves to `docs/exec-plans/completed/` with a `DISCHARGED` banner.

---

## 2. Read in this order

1. **`pending/layer0-extraction-gap-detection-decision.md`** — the source. §3.K (Q27) and §2b (Q26)
   are the two subsections that came from review rather than the interview and that supersede earlier
   text; §3.D is marked superseded and points at §3.K. Read §5 *What must not happen* before writing
   any acceptance criterion.
2. **`docs/exec-plan.md`** — the ExecPlan format you must conform to.
3. **`active/artifacts/gap-detection-probe.py`** — the measurement, executable. See §4.
4. The draft itself, last — knowing what it gets wrong (record §1) is more useful than reading it
   fresh.

Do **not** read `pending/reqs-to-data-store-plan-draft.md` (515 KB) unless something sends you there.

---

## 3. Environment

Use the venv interpreter directly. **The PATH `legacylift-search` shim is broken.**

    C:/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe

**The corpora are not in this worktree.** Only `repos/ctcm` is. NNG lives in the main checkout:

    <main>/repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app

Indexes (both outside the worktree):

    <main>/repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app/index/code-search/index.sqlite
    <main>/repos/ctcm/ctcm-api/legacylift-docs/index/code-search/index.sqlite

`ctcm-api` has **no `knowledge.sqlite`** — its `legacylift-docs/knowledge/` is empty. That is not a
defect; it makes ctcm-api the control corpus for anything involving first-party exclusions, and it
exercises predicted mode.

**I did not run the test suite.** No code changed in this work — it is all documents — so there was
nothing to regress, but that means I cannot give you a baseline. The number has moved three times
recently (357 → 408 → 521) and lives in `active/reqs-to-data-store.md`, not here and not in
`CLAUDE.md`. Take it from the plan and re-baseline before you write code.

---

## 4. The probe is committed — use it, don't rebuild it

`active/artifacts/gap-detection-probe.py` reproduces every number in §2, §2b and §3.I.

    <venv>/python.exe docs/exec-plans/active/artifacts/gap-detection-probe.py nng \
        --repo <main checkout> --vendor <path to vendor.yml>

`--repo` is required from a worktree. `--vendor` is optional (it fetches from GitHub otherwise).
Each corpus prints its expected result at the top, so a disagreement is immediately visible.

**This file exists because the previous handoff could not do this.** Its probe was ad-hoc, lived in a
session scratchpad, and had to be described in prose for the next reader to rebuild. Do not repeat
that: if you measure something the plan will assert, commit the measurement.

The probe also carries something you cannot get anywhere else — **the Q27 re-classification of NNG's
45 `domain_exclusions` patterns** into vendored / first-party, as `NNG_VENDORED` and
`NNG_FIRSTPARTY`. The live `knowledge.sqlite` still holds the un-split original, so §3.I's numbers
are not reproducible without those lists. When `/modernize-assess` is next run with the two-list
prompt, they should come from `domains.json` instead and the constants become the expected output.

---

## 5. Things that are true and easy to get wrong

- **`detect_language_from_extension` takes the extension WITHOUT a leading dot.** `("dtd")` → `dtd`;
  `(".dtd")` → `None`, silently. Get this wrong and the whole grammar column reads `-` with no error.
  `has_language()` takes a *language name*, not an extension. M0's pinned test must cover both.
- **The KB column's total must be the sum of the displayed rows**, not the true total rounded
  separately — those disagree by one on ctcm-api. §2 explains; the probe implements it.
- **`indexed` is smaller than `repo_files`** whenever a first-party exclusion exists (NNG: 871 vs
  1,229, delta 358). The report must state the reconciliation, and observed mode must not report
  those 358 as walk-vs-index discrepancies. On ctcm-api the delta is 0, which is the test.
- **Declared identity is authoritative in both directions** (§3.K): a file naming the client's own
  domain is first-party *even when a `vendored_globs` pattern claims it*. This is the only thing
  keeping `nngauthz.tld` and `naesb.tld` out of the vendored bucket, and `nngauthz.tld` declares a
  custom authorization tag bound to `com.nng.ple.web.tags.NngAuthorizeTag` — a real access-control
  rule, 1.6 KB. A real finding does not have to be a large one.
- **Do not put tier-membership rules into manifest `exclude_globs`.** The walk applies that gate
  before it tiers anything, so a rule placed there deletes the tier instead of populating it
  (measured: NNG's asset tier 89 → 0). Only `**/legacylift-docs/**` goes in the manifest.
- **`vendor.yml`'s directory-shaped patterns are not adopted.** `(^|/)[Ee]xtern(als?)?/` alone claims
  63 first-party files on NNG — the whole `com.nng.ple.*.external` integration layer.
- Grep/ripgrep honours `.gitignore`; the indexer does not. Any measurement taken with Grep sees a
  smaller tree than the walk, and they disagree on exactly the vendored content at issue. Use the
  probe.

---

## 6. Shipped alongside the record, and not obvious from it

- **`/modernize-assess` now emits two glob lists** — `exclude_globs` (first-party, not-a-capability,
  generous) and `vendored_globs` (third-party, conservative). Committed in `7b17fd0a`.
  `vendored_globs` is additive: `DomainsFile` (`domain_tagger.py:92`) sets no `extra="forbid"`, so
  pydantic ignores it, and `load_domains_json`, `tag-domains` and the coverage denominator are
  unaffected. **M1 must add the field to `DomainsFile`** when the walk starts consuming it.
- **`docs/exec-plan.md` gained two sections**, *Session handoffs* and *The `CLAUDE.md` plan index*.
  They are conventions, not suggestions, and both exist because their absence caused a measurable
  problem this week.
- **The `/handoff` skill was edited and is NOT under version control.** It lives at
  `~/.claude/skills/handoff/SKILL.md` (user-global, outside this repo). It now requires the save
  location to come from the workspace convention document or be asked for, and forbids editing
  `CLAUDE.md` or any index file as part of writing a handoff. Nothing tracks this change — if the
  file is ever reset, that behaviour is silently lost.

---

## 7. Branch state — read before merging anything

Six commits on `feature/layer0-extraction-gap-detection`, from a base of `a933bcd3`:

    58d93c40  Compress CLAUDE.md pending bullets; record the merge note
    cc4c289b  CLAUDE.md plan-index convention        (ordering: see git log)
    af3b1a6b  Six mechanical corrections at source
    7b17fd0a  assess two-list split; both-sides; §3.I repinned
    17a36b17  Q27 — two axes; provenance read, not guessed
    139f0af8  CLAUDE.md corrections
    38a9a29a  Accuracy review + Q26

`feature/reqs-to-data-store` has moved independently and edited the same files. **The merge note is
§10 of the discharged review handoff, in `completed/`** — four decisions, three of which git will not
show as conflicts, including an append-only file that has forked and must be unioned rather than
chosen. Read it before merging either branch.

---

## 8. Suggested skills

- **`citation-validator`** — the plan you write will carry file:line citations; this validates them
  against the codebase. Line numbers rotted twice in the record (`cli.py:272`, `store.py:1064-1065`).
- **`code-review`** once M0/M1 have code. Not before — there is nothing to review in a plan document,
  and the review that produced the record found its real defects by *running probes*, not by reading.

Do **not** invoke `/modernize-*` commands; nothing here runs against a legacy system.

---

## 9. Definition of done

`pending/layer0-extraction-gap-detection.md` is a conforming ExecPlan per `docs/exec-plan.md`, with a
Plan of Work, Concrete Steps and acceptance criteria for M0–M4, pinning both corpora from record
§3.I. The decision record stays where it is as the audit trail — do not fold it in, and do not
duplicate its content into the plan; reference it, following the
`reqs-to-data-store-additional-info.md` precedent.

Then move the plan from `pending/` to `active/`, update the `CLAUDE.md` row to a pointer per the new
convention, and move this handoff to `completed/` with a `DISCHARGED` banner.

---

## 10. Addendum, written on discharge (2026-09-01)

**The baseline §3 could not give you.** The suite is **408 collected, 408 passing, exit 0** on
`feature/layer0-extraction-gap-detection`, and it takes upwards of fifteen minutes. §3 said to take
the number from `active/reqs-to-data-store.md`; that would have been wrong here, because that plan's
count is for its own branch. The number now lives in the plan's `Progress`, where it belongs.

**Getting it required fixing a trap §3 half-named.** §3 says to use the venv interpreter directly.
What it does not say is that the venv exists only in the main checkout and its editable install
resolves `legacylift_search` to the *main checkout's* `src/` — a different branch. Running `pytest`
from this worktree therefore tests code you did not write: four tests failed that way and passed once
`PYTHONPATH="$PWD/src"` was set. The plan's `Concrete Steps` carries the fix and the verification
one-liner.

**What was measured, so a later pass does not repeat it.** Both corpora were re-run with the
committed probe and reproduce §3.I exactly, including the ctcm-api rounding case that distinguishes
the two KB conventions (displayed rows 21,918; separately-rounded total 21,917). Each third-party
drop was attributed to the rule that made it — NNG 29 declared-identity / 12 `vendor.yml` / 31
`vendored_globs`; ctcm-api 3 / 2 / 0 — which is the evidence behind the plan's `--json` requirement
that every drop names its rule. Both upstream linguist files were fetched and every resolution the
plan pins was verified: 833 languages, 1,486 extension keys, 419 filename keys, 168 `vendor.yml`
regexes splitting 113 filename / 55 directory.

**What was not done, deliberately.** `citation-validator` was not run; the plan's file:line citations
were verified by opening each file instead, which is what §8's own reasoning recommends. `code-review`
was not run, per §8 — there is no code yet.

**Files this session touched, for the merge note in §7.** The plan moved
`pending/` → `active/`; the decision record's header and §6 were updated to say the rewrite is done;
inbound links in `pending/deferred-small-items.md`, `pending/durable-loc-counts.md`,
`pending/embed-everything-evaluation.md` and the discharged review handoff were repointed at the new
location; `CLAUDE.md` gained an active-plan row and lost the pending bullet, with "Four pending
deliverables" corrected to "Three". **The prose references inside `active/reqs-to-data-store.md` and
`active/reqs-to-data-store-additional-info.md` still say `pending/layer0-extraction-gap-detection.md`
and were left alone on purpose** — both files are edited heavily on `feature/reqs-to-data-store`, and
a cosmetic path fix there buys a merge conflict in a 446 KB file. Fix them on whichever branch merges
second.
