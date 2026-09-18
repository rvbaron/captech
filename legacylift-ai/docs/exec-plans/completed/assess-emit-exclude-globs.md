# Teach `/modernize-assess` to Author `exclude_globs` (and Gitignore-Compatible Globs)

> **Status: COMPLETE (2026-07-24).** All five milestones done on `fix/assess-emit-exclude-globs`.
> Skill edits (M1–M4) landed; the `exclude_globs` **tier itself** shipped earlier in
> `legacylift-search` (commit `98f2f9bf`), and this plan made `/modernize-assess` *produce* it and
> taught `/modernize-map` to bucket it. M5 dry-run on NNG PASSED both halves (see Progress + the NNG
> §M5 report). Ready to move to `docs/exec-plans/completed/`.

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and
`Outcomes & Retrospective` current. Maintain per `docs/legacylift/exec-plan.md`.


## Purpose / Big Picture

The excluded-by-design domain tier now exists end-to-end in `legacylift-search`: `domains.json` may
carry a top-level `exclude_globs` array, matches become reserved `file_domains.domain='excluded'`
rows, and coverage% drops excluded files from its denominator so only true gaps (`unassigned`) fire
the "re-run assess" hint. On the NNG app this turned a dishonest 69% into an honest 100% by excluding
383 test/ops-SQL files.

But `/modernize-assess` — the skill whose domain-analysis subagent authors `domains.json` — does not
yet know about `exclude_globs`. Today it only emits `path_globs`, so everything not matched by a
domain lands as `unassigned`, conflating real coverage gaps with intentionally-out-of-scope files
(tests, ops SQL, generated code). The NNG run had to hand-author `exclude_globs` after the fact.

A second, independent gap surfaced the same session: the globs the subagent writes must be
**gitignore-compatible** (pathspec `GitWildMatch`, which `legacylift-search` uses to match), and that
syntax has **no `{a,b}` brace expansion**. The NNG session had to manually expand braces (e.g.
`config/hbm/{standard,nonstandard,external}/**`) into separate entries before `tag-domains` would
match them.

After this change, the assess domain-analysis subagent authors both `path_globs` and `exclude_globs`
in one pass, using only gitignore-compatible glob syntax — so a fresh `assess → tag-domains` run
produces honest coverage with no manual post-editing.


## Progress

- [x] Milestone 1: Add `exclude_globs` to the `domains.json` schema example + prose in `modernize-assess.md`
- [x] Milestone 2: Instruct the domain-analysis subagent to classify not-a-capability files (tests, ops/build SQL, generated code) into `exclude_globs`
- [x] Milestone 3: Add the gitignore-compatibility rule (pathspec GitWildMatch, NO brace expansion) to both `path_globs` and `exclude_globs` guidance
- [x] Milestone 4 (revised — see Decision Log): teach `/modernize-map` to READ `exclude_globs` and bucket matches into `dom:excluded`, mirroring the knowledge store, so its topology no longer mislabels excluded files as `unassigned` — the real drift risk, not glob syntax
- [x] Milestone 5: Dry-run on NNG (both units) — confirmed. Half 1: `tag-domains` from the folder's
  `domains.json` reproduces `846 glob-matched / 383 excluded / 0 unassigned / 100% coverage`, with
  `excluded` a separate axis in `validate`+`stats`. Half 2: a fresh `legacy-analyst` given only the
  updated instruction autonomously emitted brace-free `exclude_globs` that resolve to
  `845/384/0 unassigned / 100%` against the real 1229-file set — zero manual edits. Report:
  `repos/nng-app-legacylift-analysis/analysis-domains-enhanced/DOMAIN-ENHANCEMENTS-TEST-REPORT.md` §M5.


## Surprises & Discoveries

- **The original Milestone 4 targeted the wrong drift (review finding, 2026-07-24).** As drafted,
  M4 only proposed adding the gitignore-compat *note* to `modernize-map.md`. But map assigns leaf
  modules by `path_globs` only and dumps everything unmatched into `dom:unassigned`
  (`modernize-map.md`, "Group leaf modules …") — it had **no concept of `exclude_globs`**. So the real
  divergence was semantic: the knowledge store would tag a test/ops-SQL/generated file `excluded`
  while map's topology tagged the same file `unassigned`. The gitignore note is also low-value for
  map, which only *interprets* globs assess already brace-expanded, never authors them. M4 was
  rewritten to teach map to read `exclude_globs` and bucket matches into `dom:excluded`.


## Decision Log

- Decision (from the shipped tier, restated here as the contract to author against): precedence is
  **manual > domain `path_globs` > `exclude_globs` > unassigned**. A domain always wins over an
  exclusion, so a broad exclusion can never hide a domain file. The subagent can therefore write
  generous `exclude_globs` (e.g. `**/test/**`) without fear of masking a real domain file.
  Date/Author: 2026-07-24 / draft (design from `[[domain-excluded-by-design-tier]]`)

- RESOLVED (was open question): `exclude_globs` lives **only in `domains.json`**, not in the prose
  Architecture-at-a-Glance table. The code settles it — `render_architecture_mermaid`
  (`domain_tagger.py`) excludes both the `unassigned` and `excluded` slugs from nodes, and exclusions
  carry no `domains[]` entry. The "single domain set" contract ties the prose table 1:1 to `domains[]`
  by design, and exclusions are not domains. The assess skill text now says this explicitly (Step
  "Single domain set" note) so a reviewer won't "fix" the perceived table↔json mismatch.
  Date/Author: 2026-07-24 / implementation

- Decision (Milestone 4 rewrite): the drafted M4 (add gitignore-compat note to map) was replaced by
  teaching map to consume `exclude_globs` into a `dom:excluded` container. Rationale in
  Surprises & Discoveries — map's real drift risk was semantic bucketing, not glob syntax.
  Date/Author: 2026-07-24 / implementation (review finding)


## Context and Orientation

Key file: `.claude/skills/code-modernization/commands/modernize-assess.md`.

- The domain-analysis instruction to the first `legacy-analyst` subagent lives around lines 160–170:
  "for each domain, provide a small set of repo-relative path globs … every source file should match
  some domain's globs … Files not matched by any globs will surface as unassigned gaps." This is
  where the exclude-globs concept and the gitignore-syntax rule must be added.
- The `domains.json` schema example is at lines 252–268 (currently `schema_version`, `assess_run_id`,
  `domains[]` with `path_globs`, `edges[]`). `exclude_globs` is a **top-level** array, sibling to
  `domains`/`edges`.
- The "Single domain set" contract (lines 272–279) explains that the prose table and `domains.json`
  are two renderings of one list; the exclusions note must slot in without contradicting it.
- Downstream consumer: `legacylift-search tag-domains` ingests `domains.json` (matcher = pathspec
  `GitWildMatch`). `/modernize-map` (`commands/modernize-map.md`) groups topology by the same
  `domain_id`s and restates the domain-set contract — check it for the same guidance.

**Apache-2.0 attribution:** every file under `.claude/skills/code-modernization/` requires the
`Modified by CapTech on [date]: [desc].` line after the YAML frontmatter when edited (see CLAUDE.md).
Both `modernize-assess.md` and any touched `modernize-map.md` need it.

Memory: `[[domain-excluded-by-design-tier]]`, `[[domain-set-canonical-flow]]`.


## Plan of Work

**Step 1 — schema.** In the `domains.json` example (assess lines 252–268) add a top-level
`"exclude_globs": ["**/test/**", "**/*Tests/**", "db/migrations/**", "**/generated/**"]` entry with a
one-line prose note explaining it marks intentionally-out-of-scope files (tests, ops/build SQL,
generated code) that count as `excluded`, not `unassigned`. Use generic placeholders consistent with
the skill's existing `src/Claims/**` examples — no repo-specific paths.

**Step 2 — subagent instruction.** Extend the lines 160–170 domain-globs instruction: after asking
for per-domain `path_globs`, ask the analyst to also identify files that are legitimately **not a
business capability** and author `exclude_globs` for them, so they don't drag coverage down or fire
the re-run hint. State the precedence (domain wins over exclusion) so exclusions can be generous.

**Step 3 — gitignore-compat rule.** Add, adjacent to both glob instructions, an explicit constraint:
"Globs are matched with gitignore semantics (pathspec GitWildMatch). Use `**`, `*`, `?`, and
character classes — but NOT `{a,b}` brace expansion; write each alternative as its own entry
(`config/hbm/standard/**`, `config/hbm/nonstandard/**`, …)."

**Step 4 — map parity (revised).** `modernize-map.md` restates the domain-set contract in its "Group
leaf modules under `domain` containers" bullet, assigning modules by `path_globs` and bucketing the
rest as `dom:unassigned` — with no `exclude_globs` awareness. Teach it to route modules that match an
`exclude_globs` entry (and no domain glob) into a `dom:excluded` container mirroring the knowledge
store's `excluded` bucket, and to state the domain > exclude > unassigned precedence. (The gitignore
note is folded in as a one-liner, but the substantive fix is the bucket.)

**Step 5 — attribution + dry run.** Add/refresh the CapTech attribution line on each edited file.
Run `/modernize-assess` (or just the domain-analysis step) against a test repo, then `tag-domains`,
and confirm `validate`/`stats` report `excluded` separately with no manual glob editing.


## Validation and Acceptance

1. `modernize-assess.md` documents `exclude_globs` in both the schema example and the prose.
2. The domain-analysis instruction tells the subagent to classify not-a-capability files into
   `exclude_globs`, and states the domain-wins-over-exclusion precedence.
3. Both glob instructions state the gitignore-compatibility rule and explicitly forbid brace expansion.
4. `/modernize-map` guidance is consistent (no divergent glob advice).
5. A fresh `assess → tag-domains` on a test repo yields `excluded` files with zero manual glob edits;
   coverage% reflects the honest (discovered − excluded) denominator.
6. CapTech Apache-2.0 attribution line present/current on every edited skill file.


## Idempotence and Recovery

Edits are to skill markdown only — re-running the plan overwrites text deterministically; no data
migration. If a dry run shows unmatched globs, the fix is in the skill prose (or the emitted
`domains.json`), not in `legacylift-search`, which already supports the tier.
