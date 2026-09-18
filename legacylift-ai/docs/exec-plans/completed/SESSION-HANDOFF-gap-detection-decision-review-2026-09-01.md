# Session Handoff — review the extraction-gap decision record (2026-09-01)

> **DISCHARGED 2026-09-01. This file is history; do not work from it.**
> The review ran and the record survived — see §10 for the five commits, the two design
> changes (Q26, Q27) and the six mechanical corrections. §4's list of unverified claims is
> resolved and must not be re-litigated.
>
> **§10 also carries the merge note**, which is NOT history: two branches edited `CLAUDE.md`
> and `pending/` from a common base without seeing each other, and three of the four things
> that need deciding will not appear as git conflicts. Read it before merging either branch.
>
> The live next action is the plan rewrite —
> `active/SESSION-HANDOFF-gap-detection-plan-rewrite-2026-09-01.md`.

**Your job:** review
[`layer0-extraction-gap-detection-decision.md`](../pending/layer0-extraction-gap-detection-decision.md) for
**consistency, completeness and accuracy**. It is a sign-off document: the plan
[`layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md) is about to be rewritten
from it, so an error there becomes an error in the ExecPlan and then in the code.

**Read §3 and §4 of this handoff before you start.** §3 lists what has already been verified with a
reproducible probe — re-verifying it wastes your pass. §4 lists what was *not* verified, and is where
your value is highest.

You are reviewing a **document**, not code. There is no code for this plan yet.

---

## 1. What to review, and where it is

Worktree `C:\Users\dnorton\captechdev\legacylift-ai\.claude\worktrees\layer0-gap-detection`, branch
`feature/layer0-extraction-gap-detection`, based on `a933bcd3`.

```
git log --oneline a933bcd3..HEAD
git diff a933bcd3..HEAD
```

| Commit | Contents |
|---|---|
| `393de08f` | Two new pending drafts, the standing small-items list, `modernize-status.md` §2 rule, `CLAUDE.md` |
| `f57c65fe` | **The decision record — the primary review target** |

Secondary targets, in scope because the record cross-references them and they were written in the
same session: `durable-loc-counts.md`, `embed-everything-evaluation.md`, `deferred-small-items.md`,
the `CLAUDE.md` pending-deliverables block, and the `modernize-status.md` §2 addition.

The commit messages carry the reasoning; read them first.

---

## 2. How the record was produced, and what that implies

A structured design interview across 2026-08-31 and 2026-09-01: five rounds, twenty-five numbered
decisions, each put to the user with a recommendation and explicitly approved. §4 of the record is a
25-row index; §3 is the settled design organised by topic.

Two consequences for your review:

- **The decisions themselves are not up for re-litigation.** The user approved each one. If you think
  a decision is wrong, say so with evidence and let the user decide — do not treat it as a defect.
- **The measurements are absolutely up for challenge.** Every number in §2 of the record is pinned as
  an acceptance criterion in §3.I. If a number is wrong, the acceptance criteria are wrong.

The record also asserts that the existing draft is wrong in six places (§1). Those claims are the
highest-stakes content in the document: if any correction is itself mistaken, the rewrite will damage
a plan that was previously right.

---

## 3. Already verified — do not re-verify

Each of these was measured in-session against real corpora, not reasoned about:

| Claim | How it was checked |
|---|---|
| `include_globs` is the gate; the `detect_language is None` branch is unreachable under default config | Read `discovery.py:63-80` + `config.py:21-52`; every default include glob maps to a registered extension |
| Nothing reads `.gitignore` | `grep -rn gitignore` over `src/` — only `pathspec` dialect names |
| Claude Code's Grep **is** ripgrep and honours gitignore | Empirical: a string present in a gitignored `.venv` file returns "No files found" via Grep, `1` via bash `grep -c` |
| linguist `languages.yml`: 833 languages, 1,486 extensions, `.jsp` → Java Server Pages/programming, `.tld`/`.jspf`/`.vm` absent, all binaries absent | Fetched and parsed with `yaml.safe_load` |
| linguist `filenames:` = 419 entries; `Jenkinsfile` → Groovy/programming | Same parse |
| tree-sitter pack exposes `detect_language_from_extension`, 306 languages, `.jsp`/`.tld`/`.xsd` → `None`, `.dtd` → `dtd` | Called the API in the venv |
| The four-tier NNG walk and its exact totals (record §2) | Ad-hoc probe; tiers sum to the walk total, `reconciles=True` |
| Check two: 8 files on NNG, 0 on ctcm-api | SQL, reproduced below |
| scc 3.7.0 reports 1,541 files vs the walk's 1,765, omitting `.tld`/`.vm`/`.ent`/dotfiles | Ran `scc --no-cocomo` |
| `MAX(chunks.end_line)` = real line count for 1,173/1,229 NNG files; Java aggregate 135,824 vs scc 135,829 | Compared against `sum(1 for _ in open(p,'rb'))` per file |
| Embed filter drops 69.1% (NNG) / 70.7% (ctcm-api); Chroma holds 4,651 / 17,212 vectors | Recomputed `should_embed` over stored chunks; counted `embeddings` in `chroma.sqlite3` |
| 174 NNG symbols carry unprefixed Webflow kinds | `SELECT kind,COUNT(*) FROM symbols GROUP BY kind` |
| `pyyaml` is not a runtime dependency; both real manifests set `embed_min_tokens: 80` | Read `pyproject.toml` and both `manifest.snapshot.json` |

---

## 4. NOT verified — where your value is highest

Ordered by risk. These are known gaps, not suspicions.

**4.1 — Titan pricing is unverified and load-bearing.** `embed-everything-evaluation.md` states
"$0.02/M tokens" and derives its central claim (the filter saves ~half a cent per repository) from it.
That figure came from model memory and was **never checked against AWS pricing**. If it is wrong by an
order of magnitude the plan's argument changes. Verify or mark it as an estimate. The *token* deltas
(+94,189 NNG, +254,827 ctcm-api) were measured and are sound; only the dollar conversion is suspect.

**4.2 — The Qwen 350 ms/chunk rate is inherited, not re-measured.** The "~44 minutes of extra local
CPU embedding" in the same plan derives from a rate recorded in an earlier session's memory. Not
re-measured here.

**4.3 — An unexplained 18% discrepancy on ctcm-api.** Recomputing `should_embed` over stored chunks
predicted 14,093 distinct embedded chunks; the live Chroma store holds 17,212. NNG agreed closely
(4,507 predicted vs 4,651 actual, ~3%). The ctcm-api gap is not explained anywhere. It does not change
the ~70% headline, but it means the recomputation is not a faithful model of what the indexer did, and
something is unaccounted for.

**4.4 — The PRINCIPLE-1 invocation may be loose.** The decision record §3.E says the classification
columns are "fact lookups rather than inferences, so PRINCIPLE-1's marking burden is light". That
phrasing was inherited from the original draft. The actual NORMATIVE text lives in
`pending/reqs-to-data-store-plan-draft.md` and, as restated in `active/reqs-to-data-store.md`, reads
closer to *"infer once, at the point of maximum evidence"* — which is not obviously a rule about
marking inferences at all. **Read the NORMATIVE section and confirm the invocation is correct**, in
both the decision record and the original draft.

**4.5 — The asset and credential extension lists are invented.** `CRED_EXT` (`.p12 .jks .keystore
.pfx .pem .cer .crt`), `CRED_FN` (`ssTrustStore cacerts truststore keystore`) and the asset list were
authored during the interview and validated only against NNG, where they happen to be exactly right
(4 credential files, 89 assets). They have not been tested against ctcm-api or any other tree. A
false positive here silently moves a real source file out of the findings — the failure this whole
plan exists to prevent.

**4.6 — Line-count method may not match `wc -l`.** All line counts use
`sum(1 for _ in open(p,'rb'))`, which counts lines by iteration. A file lacking a trailing newline can
differ from `wc -l` by one. Across 1,765 files this could shift the pinned totals slightly. Decide
whether the acceptance criteria should specify the counting method.

**4.7 — The pinned acceptance numbers are known to be invalidated by M4.** By design: M4 adds asset
globs to the manifest defaults, moving the tier boundaries. The record says M4 must restate them
(§3.I). Check that this is stated clearly enough that an implementer does not treat an M4 test failure
as a regression.

**4.8 — ctcm-api has no tier walk.** Check two was run there (0 files, the discriminating negative),
but the four-tier walk was only ever run on NNG. Whether the tier design behaves sanely on a C#
codebase is unknown.

---

## 5. Environment and reproduction

**Do not use the `legacylift-search` PATH shim — it is broken.** Use the venv binary directly:

```
C:/Users/dnorton/captechdev/legacylift-ai/tools/legacylift_search/.venv/Scripts/python.exe
```

Baseline test suite is **357/357 passing, exit 0**; fewer means you caused a regression, not an
environmental failure. (That baseline predates the concurrent M0 work in §6 — re-baseline before
drawing conclusions.)

**The NNG corpus is not in this worktree.** Only `repos/ctcm` is checked out here. NNG lives in the
main checkout:

```
C:/Users/dnorton/captechdev/legacylift-ai/repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app
```

Indexes (both outside the worktree):

```
.../repos/nng-app-legacylift-analysis/analysis/customer.ple.nng.app/index/code-search/index.sqlite
.../repos/ctcm/ctcm-api/legacylift-docs/index/code-search/index.sqlite
```

**Check two**, reproducible directly:

```sql
SELECT f.relative_path, f.language, f.size_bytes FROM repo_files f
  LEFT JOIN symbols s ON s.file_id = f.id
  GROUP BY f.id HAVING COUNT(s.id) = 0 AND f.size_bytes >= 2048
  ORDER BY f.size_bytes DESC;
```

**The tier walk probe was ad-hoc and is NOT committed** — it lived in a session-local scratchpad that
no longer exists for you. To reproduce record §2: walk the corpus with `Path.rglob("*")`, apply
`ProjectConfig().exclude_globs` via `pathspec` (gitignore dialect), then bucket each surviving file by
the precedence in record §3.D — `indexed` if it matches `include_globs`, else `credential` if its
extension or filename is in the credential sets, else `excluded` if its extension is an asset type,
else `gap`. Count files, `st_size`, and lines per bucket. Assert the buckets sum to the walk total.

**Linguist data** is not vendored yet (that is M0). Fetch from
`https://raw.githubusercontent.com/github-linguist/linguist/main/lib/linguist/languages.yml` and
`.../vendor.yml`. MIT © GitHub.

---

## 6. Concurrent work — do not touch

A **separate session is actively working in the main checkout** on Milestone 0 of
`active/reqs-to-data-store.md`: roughly 1,119 uncommitted lines across `identity.py`,
`test_identity.py`, `test_migrations.py`, `cli.py`, `cli_helpers.py`, `config.py`, `indexer.py`,
`store.py`. None of it is yours and none of it is in this worktree. The main checkout also still holds
four files authored in this session (`CLAUDE.md` plus the three new `pending/` drafts) that the other
agent was asked to clean up so there are no mixed-plan commits — if you see them there, leave them
alone.

`main` is **176 commits behind** and has none of this: no `reqs-to-data-store.md`, no
`layer0-extraction-gap-detection.md`, not even `modernize-status.md`. Do not branch from it or diff
against it.

---

## 7. Specific consistency checks worth running

- **Arithmetic.** Record §2's tiers must sum to 1,765 / 8,923 KB / 206,244 lines, and 443 + 89 + 4 =
  536 must match the raw pre-suppression gap quoted in §1d and in `CLAUDE.md`.
- **The 25-row index (§4) against the prose (§3).** Every decision should appear in both, saying the
  same thing. This is the most likely place for internal drift.
- **Cross-document agreement.** `CLAUDE.md`'s extraction-gap bullet, the decision record, and (after
  rewrite) the plan must not state different figures. `CLAUDE.md` currently says "Design settled
  through Q1–Q10 … Q11–Q13 still open" — **that is now stale; all 25 are settled.** Confirm and fix.
- **Every file:line citation.** The record cites `discovery.py:63-80`, `config.py:21-52`,
  `config.py:55`, `config.py:95`, `config.py:145`, `store.py:1047-1050`, `store.py:1064-1065`,
  `cli.py:272`, `cli.py:1728`, `indexer.py:921`, `xml_extractor.py:245`, `xml_extractor.py:251-253`.
  Spot-check them; line numbers rot.
- **Completeness against the source draft.** The original draft's "Open questions the design
  conversation has to settle" has four headings — *where it lives*, *whether it gates anything*, *how
  the exclusion list is expressed*, *whether it should propose*. Confirm all four are answered and
  that the record's "what must not happen" carries all three of the draft's originals forward.

---

## 8. Suggested skills

- **`code-review`** — the natural fit for the diff-shaped part of this. Invoke as
  `/code-review a933bcd3..HEAD high`. It is tuned for code rather than prose, so treat its output as
  one input, not the review.
- **`citation-validator`** — purpose-built for exactly §7's fourth bullet: validating line-number
  references in documentation against the actual codebase. This is the highest-leverage skill here.
- **`documentation-review`** — reviews generated documentation for accuracy against source code.
  Applicable to the record's claims about `discovery.py`, `embed_filter.py` and `xml_extractor.py`.
- **`Explore` agent** — for the cross-document consistency sweep in §7, which spans `CLAUDE.md`, four
  `pending/` files and two `active/` plans.

Do **not** invoke `/modernize-*` commands; nothing here runs against a legacy system.

---

## 9. Definition of done

A findings list, most-severe first, distinguishing:

1. **Factual errors** — a measurement, citation or claim that is wrong. These block the rewrite.
2. **Internal inconsistencies** — §3 disagreeing with §4, or the record disagreeing with `CLAUDE.md`.
3. **Completeness gaps** — a settled decision that is missing, or an open question left unanswered.
4. **Unsupported claims** — §4 above is the known set; add anything else you find asserted without
   evidence.

If the record survives, say so plainly — the next action is the plan rewrite described in record §6,
and a clean review is what unblocks it. When this handoff is discharged, move it to
`docs/exec-plans/completed/` with a `DISCHARGED` banner, following the convention of the three
existing `SESSION-HANDOFF-*` files.

---

## 10. Review discharged 2026-09-01 — and a merge note that outlives it

The review ran. The record survived, with two design changes (**Q26**, **Q27**) and six mechanical
corrections, all committed on `feature/layer0-extraction-gap-detection`:

| Commit | What |
|---|---|
| `38a9a29a` | The review, and **Q26** — a fifth `referenced content` tier; `**/legacylift-docs/**` into the manifest defaults; acceptance pinned on both corpora |
| `139f0af8` | Three errors in `CLAUDE.md`'s extraction-gap bullet |
| `17a36b17` | **Q27** — exclusion has two axes; provenance is read, not guessed; the `domain_exclusions` provenance finding |
| `7b17fd0a` | `/modernize-assess` emits two glob lists; first-party exclusion applies to both sides; §3.I repinned |
| `af3b1a6b` | The six mechanical corrections, fixed at source |

Record §6 is the live next action: rewrite the draft into a conforming ExecPlan. Nothing blocks it.

Of the eight items §4 above flagged as unverified, three resolved clean and are recorded as such in
the commits: Titan is $0.02/M (correct); the "unexplained 18% ctcm-api discrepancy" is not one (the
recomputation matches Chroma exactly — 14,093 counts distinct `text_sha256` representatives, and
`dedupe_by_text_sha` fans each vector out to every member id); and the PRINCIPLE-1 invocation is
correct. §4.5's worry about the invented extension lists was right, but not where it expected: the
lists were exactly right on NNG and wrong on ctcm-api, which is what Q26 exists to fix.

### The merge note — read this before merging either branch

This branch and `feature/reqs-to-data-store` both edited `CLAUDE.md` and `pending/`, from a common
base of `a933bcd3`, without seeing each other. Four things need a decision at merge, and three are
not textual conflicts git will show you.

1. **Delete the "two of the four have no file on disk yet" paragraph** from the reqs branch's
   `CLAUDE.md` pending block. It states — dated, and marked *verified* — that
   `pending/durable-loc-counts.md` and `pending/embed-everything-evaluation.md` do not exist. Both
   exist, committed here in `393de08f` (112 and 126 lines). The check was real; the conclusion was
   false because it ran against one working tree. **A claim about the repository's contents made from
   a single working tree is not verified** — that is the durable lesson, and why the paragraph must
   be deleted rather than reconciled.
2. **Take the two active-plan table rows from `feature/reqs-to-data-store`.** That branch compressed
   the `reqs-to-data-store` row from 342 words to 114 and reached the right principle independently:
   *"This plan is the definitive record of its own state — milestone progress, test counts, next
   action and the `CR-` code-review series all live in it, not here."* Better than what this branch
   carries; take it wholesale.
3. **Take the pending bullets from this branch.** The reqs branch's copies are stale in exactly the
   ways this review corrected — `31 extension patterns` (it is 27, five of them path patterns) and
   "Design settled through Q1–Q10; Q11–Q13 still open" (all 27 are settled). Its bullet also points
   at a companion record that does not exist on that branch.
4. **`deferred-small-items.md` has forked, and must be unioned, not chosen.** Same path, different
   first entry — this branch has `/modernize-status` §4 and the unprefixed Webflow kinds; the reqs
   branch has the ten nullable `TEXT PRIMARY KEY` columns. The file is declared append-only, so
   taking either side silently drops real measured findings. Merge all three entries and renumber.

### The standing lesson, now measured twice

Neither the handoff convention nor the `CLAUDE.md` convention was written down. The first gap put
`SESSION-HANDOFF-*` files in three different folders. The second had two sessions independently
reinvent the same rule — one well, one with a confident false claim about files it could not see.
`docs/exec-plan.md` now carries the handoff convention, added this session. The `CLAUDE.md` one is
still unwritten, and the paragraph it needs is short: **a `CLAUDE.md` plan row is a pointer, not a
summary — name, status, next action, one gate; durable detail belongs in the plan's own `Progress`,
`Decision Log` and `Surprises & Discoveries`, where it cannot drift.**
