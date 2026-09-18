# Extraction gap detection — design record

**Status: DECISION RECORD — design settled; the plan it fed has been written.** Companion to
[`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md), which
was rewritten from this record on 2026-09-01 and is now a conforming ExecPlan. **That plan is the
live document — build from it, not from this one.** This file records the twenty-seven decisions
that settled its design, the measurements behind them, and the alternatives that were rejected — so
that a later reviewer does not reopen settled ground. It follows the precedent of
`active/reqs-to-data-store-additional-info.md`: consult it before proposing a change the interview
may already have rejected.

Two consequences of the rewrite for anyone reading this record on its own. **§1 *Corrections to the
draft* is now history** — every correction it lists was applied when the plan was rewritten, so the
"five load-bearing places" it names are places the plan is now right about, not places it is wrong.
And **two rounded values in §3.I's NNG table are stale**: `gap` is 805 KB, not 804, and `asset` is
1345 KB, not 1344, which is why that column fails the sum-to-total property §2 requires. Re-measured
2026-09-01 with the committed probe; the plan carries the corrected figures.

Produced by a design interview on 2026-08-31 and 2026-09-01: five rounds, twenty-five decisions, all
approved. **Q26 and Q27 were added on 2026-09-01 by the independent accuracy review** that this
record was handed off for — the first pass to run the tier rules against a corpus other than NNG, and
the first to ask where the exclusion lists came from. They are the two decisions here that did not
come from the interview, and **Q27 supersedes Q4**. Every number below was measured against
`repos/nng-app-legacylift-analysis/legacy/customer.ple.nng.app` and `repos/ctcm/ctcm-api`, not
estimated.

---

## 1. Corrections to the draft

These are not refinements. Each one changes what gets built.

**1a — The cause is `include_globs`, not `detect_language`.** The draft says "The cause is one
branch… `detect_language` returns `None` for any extension not in `_EXTENSION_TO_KEY`."
`discover_source_files` (`discovery.py:63-80`) applies three gates in order: manifest
`exclude_globs`, then manifest `include_globs`, then `detect_language`. `include_globs`
(`config.py:21-52`) is an explicit **allow-list of 27 globs** — 22 `**/*.ext` patterns and 5 path
patterns (`**/*-flow.xml`, `**/flows/**/*.xml`, `**/applicationContext*.xml`, `**/spring/**/*.xml`,
`**/config/**/*.xml`) — and every default entry
maps to an extension that *is* in `_EXTENSION_TO_KEY`. **Under default config the
`detect_language is None` branch is unreachable.** Every extension in the draft's own measurement
fails at the include gate, two steps earlier.

**1b — The draft's specification for check one returns the empty set.** It requires walking "under
the same include/exclude rules `discover_source_files` applies". Applying an allow-list and then
looking for what the allow-list rejected yields nothing by construction. The check must deliberately
drop the include gate (Q1).

**1c — Nothing in the toolchain reads `.gitignore`.** The draft requires "the same `.gitignore` and
manifest exclusion handling the discovery path uses". Discovery honours manifest globs only; the
string `"gitignore"` at `discovery.py:51-52` is `pathspec`'s syntax-dialect name. No `.gitignore` is
read anywhere in `legacylift_search`. A related trap: any agent measuring this gap with Grep/ripgrep
*does* inherit gitignore filtering, so it measures a smaller tree than the indexer walks, and the two
disagree on exactly the vendored/build content at issue.

**1d — The draft's numbers are roughly 2× too high.** It counted files that manifest `exclude_globs`
already drops — `bin/main/` and `target/` build duplicates — which is the precise mistake it warns
against elsewhere ("or it will report `node_modules` and build output as findings").

| | draft | measured |
|---|---|---|
| `.jsp` | 364 files, 1276 KB | **186 files, 682 KB** |
| `.tld` | 24 files, 494 KB | **13 files, 278 KB** |
| `.xsd` | 14 files, 264 KB | 14 files, 264 KB ✓ |

**1e — There are already two exclusion vocabularies, not one.** The draft treats `domains.json`
`exclude_globs` as the candidate for reuse. Manifest `exclude_globs` (`config.py:55`) also exists and
is the one discovery actually applies; `domains.json` exclusions are reached separately via
`KnowledgeStore.list_exclusions()` (`cli.py:310`, `indexer.py:1003`).

**1f — Check two's measurement is confirmed.** Re-run 2026-09-01: `repo_files LEFT JOIN symbols` with
zero symbols and `size_bytes >= 2048` returns **8 files on NNG** (7 SQL, 1 XML; largest
`ple-persistence/sql/FarmTapEntry.sql` at 5,876 bytes) and **0 on ctcm-api**. The draft was right,
and the negative result is what proves the check discriminates rather than always firing.

---

## 2. The measurement, restated

Walking the NNG app with manifest `exclude_globs` applied and the settled tier rules, counting files,
bytes and lines in one pass:

        TIER          files       KB      lines
        indexed        1229     5605     149673
        gap             443     1894      49202
        excluded         89     1384       7177
        credential        4       41        192
        WALK TOTAL     1765     8924     206244      (tiers sum exactly)

**Headline: the gap is 25.3% of bytes and 24.7% of lines**, over a denominator of indexed + gap.
Before the asset and credential tiers are separated the raw gap is 536 files / 3,318 KB — 37% of
bytes — which is the figure to quote when explaining why suppression is not cosmetic.

**Two counting conventions, stated because both were once wrong here.**

*KB.* Each row is `round(bytes / 1024)`, and **the displayed total is the sum of the displayed rows**
— not the true total rounded separately. An earlier version floored each row and the total
independently, so the column summed to 8,921 against a stated 8,923 while claiming "tiers sum
exactly", which is the one property §5 says a reader must be able to check by adding it up. Rounding
consistently is *not* sufficient on its own: measured, per-row rounding happens to sum on NNG and
does **not** on ctcm-api (21,918 against a separately-rounded 21,917), because the fractional parts
accumulate past a half. Only summing the displayed rows makes the property hold by construction.
Exact bytes belong in `--json`, where nothing is rounded.

*Lines.* `sum(1 for _ in open(path, 'rb'))`, which can differ from `wc -l` by one on a file with no
trailing newline. What matters is that one method is used on both sides of the ratio; the acceptance
criteria assume this one.

The gap tier, byte-ordered, with the two classification columns the report will carry:

        ext          files      KB   lines  linguist                       type         grammar
        .jsp           186     682   15700  Java Server Pages              programming  -
        .tld            13     279    8685  (unknown to linguist)          -            -
        .xsd            14     264    7120  XML                            data         -
        (none)          80     149    4747  (unknown to linguist)          -            -
        .dtd             4     123    3322  (unknown to linguist)          -            dtd
        .css            10      92    3666  CSS                            markup       css
        .properties     44      83    2034  INI/Java Properties            data         properties
        .xml            15      66     963  XML                            data         xml
        .txt             1      33       1  Adblock/Text/Vim Help          data/prose   vimdoc
        .ent             3      30     513  (unknown to linguist)          -            -
        .gradle         11      24     719  Gradle                         data         groovy
        .htm             4      23     434  HTML                           markup       html
        .vm             35      18     509  (unknown to linguist)          -            -
        .mf             10       9     326  (unknown to linguist)          -            -
        … 9 more, each under 4 KB

        excluded (asset):  .jpg 18/1229 KB · .png 47/62 · .gif 22/62 · .psd 1/31 · .ico 1/0
        credential:        .p12 2 files/19,806 B · ssTrustStore 2 files/22,412 B

Five things this table settles by itself:

- **Asset suppression is load-bearing, not tidiness.** `.jpg` at 1,228 KB is the largest single group
  in the whole walk. Unsuppressed, the report's top finding is a photograph.
- **The two classification columns are genuinely complementary.** `.dtd` is unknown to linguist but
  *has* a tree-sitter grammar; `.jsp` is known to linguist and has none. Neither column subsumes the
  other, and the pair is the triage.
- **`.xml` appears on both sides** — 183 indexed, 15 not. Those 15 pass `detect_language` and fail
  only `include_globs`, i.e. XML that is not `*.hbm.xml` / `*-flow.xml` / `spring/**` / `config/**`.
  The fix is "add a glob", and it was invisible before.
- **Lines re-rank the findings.** `.tld` is fourth by bytes but **second by lines** (8,685) — 13 files
  carrying more lines than 14 `.xsd` files of twice the size. **Corrected 2026-09-01 (Q27): the
  re-ranking is real, but `.tld` is the wrong example.** Reading what those files declare, 11 of the
  13 are vendored — Spring, JSTL, Tiles, displaytag, Joda — and only `nngauthz.tld` (1,630 B) and
  `naesb.tld` (920 B) are NNG's, 88 lines between them. All 14 `.xsd` are Spring's published schemas
  and all 4 `.dtd` are Hibernate's and the W3C's. So roughly **650 KB of what §2 calls the gap is
  third-party**, and the honest version of this bullet is that lines re-rank `.properties` above
  `.xml`, not that `.tld` is the second-largest finding.
- **The credential tier rescues four files** that any plausible asset denylist would have swallowed.

**Corroboration.** `scc` 3.7.0 independently reports 186 JSP and 995 Java files, matching the walk.
But **scc's total is 1,541 files against the walk's 1,765**: it silently omits `.tld` (13), `.vm`
(35), `.ent` (3) and every dotfile, because it too is an allow-list. That is why scc cannot be the
gap oracle — used as one it would hide the second-largest finding in the corpus. Two cautions on
that comparison: the 224-file difference is dominated by the 89 assets and 80 extensionless files,
not only the extensions named above, and it is **not like-for-like in both directions** — scc also
counts 12 JavaScript and ~8 XML files that manifest `exclude_globs` drops, because scc honours
`.gitignore` and not the manifest.

---

## 2b. The second corpus — where the tier rules failed (Q26)

Everything in §2 was fitted to NNG. Running the identical rules against `repos/ctcm/ctcm-api`
(measured 2026-09-01, during the accuracy review) produces a report that is worse than useless:

        TIER          files       KB       lines
        indexed        4715    11461      295488
        gap             308    40443     1059889
        excluded          0        0           0
        credential        0        0           0
        WALK TOTAL     5023    51905     1355377

        headline: 77.9% of bytes, 78.2% of lines

**A 77.9% gap headline, three times NNG's, and two extensions are 98.8% of it:**

        ext        files      KB     lines   what they actually are
        .json        103   29937   1012630   legacylift-docs/context/packs/*.facts.pack.json
        .docx         57    9969     36166   Word templates under CTCM.API.DocumentService/

The `.json` findings are **LegacyLift's own generated output**. Manifest `exclude_globs` carries
`**/legacylift-docs/index/**` but not the parent directory, so the gap report's largest finding on
this corpus is the tool's own artifacts — verbatim the failure the draft warned about ("or it will
report `node_modules` and build output as findings and be ignored within a week"). The `.docx` files
are binary zip containers, so their 36,166 "lines" are compressed noise.

Three things this settles:

- **`**/legacylift-docs/**` belongs in the manifest defaults**, widening the existing
  `**/legacylift-docs/index/**`. Verified zero index impact: `indexed` stays at 4,715 files, because
  no `.cs` file lives under it. This alone moves the headline from 77.9% to **47.9% of bytes** — and
  from 78.2% to **14.1% of lines**.
- **The tier rules need office and binary formats**, not just the five image types NNG happened to
  need. Routing `.docx .doc .xlsx .xls .pptx .ppt .pdf .zip` to the new referenced-content tier and
  `.bmp .svg .woff .woff2 .ttf .eot` to the asset tier takes ctcm-api to **3.90% of bytes / 3.81% of
  lines**, with 59 files and 10,082 KB counted and named rather than discarded. On ctcm-api all 59
  land in referenced content (58 templates plus one PDF) and the asset tier is empty — the mirror of
  NNG, where the asset tier holds 89 and referenced content is empty. Neither corpus alone would have
  produced both tiers. *(Q27 later drops a further 5 third-party files here, moving the final pinned
  figure to 3.15% / 3.14% — §3.I carries the settled numbers; these are the Q26 measurement that
  motivated the tier.)*
- **The byte and line headlines disagreeing violently is the cheap diagnostic.** 77.9% of bytes
  against 78.2% of lines looked plausible; the moment one glob moved lines to 14.1% while bytes sat
  at 47.9%, the remaining mass was obviously a handful of huge binaries. Report both, and treat a
  large divergence as a suppression bug rather than a finding. This is why Q14 (count both) earns its
  place beyond the ranking argument originally given for it.

**The general lesson, which outranks the specific globs:** every tier rule in §2 was fitted to one
corpus, and the first contact with a second corpus broke two of them. Acceptance criteria that pin
NNG alone cannot catch this (§3.I now pins both — see Q26).

---

## 3. Settled design

### A. What the check measures — Q1, Q20

The walk applies manifest `exclude_globs` and then deliberately **drops the `include_globs` gate**,
reporting what survives. Findings are labelled by *which* gate rejected them, because the fixes
differ: "not in `include_globs`" means edit the manifest; "included but no language" means write a
parser. (Q1)

Two modes, both implemented, with the mode named in the output (Q20):

- **Observed** — diff the walk against `repo_files`. Preferred when an index exists. Strictly more
  truthful: it is the only mode that sees a file dropped by the `max_file_bytes` 2 MB cap
  (`config.py:95`) or by a read error, both of which `discovery.py:81-98` swallows silently.
- **Predicted** — replicate the three gates in-process from the manifest. No database required, so
  the check is available before `index` has ever run. This is where the draft's instinct about
  `/modernize-preflight` was right.

The two can legitimately disagree; the output must say which produced the number.

### B. Home and name — Q2, Q19

A new `legacylift-search gaps` subcommand, sitting beside `stats` / `coverage` / `domains`. Not a
section of `stats` (already carrying an index table and a domain line), and not `/modernize-preflight`
(wrong lifecycle position for the observed mode). `--json` output carries `schema_version: 1`,
following `domains.json` and `profiles/extractors.json`.

### C. Scope — Q3, Q10

Both checks ship together. Check one (never indexed) and check two (indexed but symbol-less) fail in
different directions and neither subsumes the other; shipping one alone makes the other look like it
does not exist. Check two exposes `--min-bytes`, defaulting to 2048 — the floor that produced the
8-versus-0 discriminating measurement, but a corpus-specific judgment that should not be welded in.

### D. Suppression and tiers — Q4, Q12, Q15, Q22, Q26, Q27

**Superseded by Q27 (§3.K).** Q4's original wording — "three suppression sources, unioned, with the
applied set named in the output: manifest `exclude_globs`; `KnowledgeStore.list_exclusions()` when
`knowledge.sqlite` exists; and linguist's `vendor.yml`" — turned out to name three mechanisms as one
and to get `vendor.yml`'s regex count wrong (168, not 396; 396 is the file's line count). What
survives Q27: manifest `exclude_globs` and third-party provenance are **drops**; first-party
exclusions are a **named tier**; and `list_exclusions()` is not reusable as authored. Read §3.K
before implementing anything in this subsection.

**Linguist classifies and ranks; it never filters.** Absence from `languages.yml` does discriminate
binaries (`.png`, `.jar`, `.dll`, `.class`, `.exe`, `.woff`, `.pdf`, `.zip` are all absent) but it
also swallows genuine source: `.tld`, `.jspf` and `.vm` are absent too, and `.tld` includes NNG's own
`nngauthz.tld` and `naesb.tld` (Q27 — the 8,685-line figure once quoted here is 99% vendored, so use
the two first-party files as the example, not the byte total). Filtering on linguist would re-create
`include_globs` one layer up with the same
silent-drop bug. `type:` (`programming` > `markup` > `data` > `prose`) is used only for ordering.

**Five tiers, mutually exclusive, precedence
`indexed → credential → referenced content → excluded-by-design → gap`**, so the columns reconcile
to the walk total (Q22, Q26). Credential outranks the rest specifically so a keystore can never be
hidden by an image glob. The excluded tier is **counted, totalled and named, not discarded** —
following the `domain-excluded-by-design-tier` precedent, where a reserved `excluded` value distinct
from `unassigned` took NNG's domain coverage from 69% to an honest 100%. Excluded is not invisible.

**Referenced content is its own tier, above excluded** (Q26). A binary document that indexed code
resolves *by name* is not an asset, and collapsing it into the image bucket destroys the only
interesting thing about it. Measured on ctcm-api: of the 58 template files under
`CTCM.API.DocumentService/Templates/` (57 `.docx` + 1 `.doc`), **57 are named in indexed C# source**,
bound by a constants class — `CTCM.API.Shared/Dto/Document/TemplateNames.cs` carries all 57 as
`public const string BenefitAddendum = "BenefitAddendum.docx";` — and
`MergeClassAttribute.cs:12` states the contract explicitly: *"Required for finding proper template.
Must be titled exactly like file."* Zero `.docx` rows exist in `repo_files`.

So each of those files sits on the far end of a real code→content edge that the index cannot
currently see. The tier reports, per file: the count of indexed code references resolving to it, and
a flag when that count is **zero**. The tier holds 59 files on ctcm-api — the 58 templates plus one
PDF elsewhere in the tree — and **exactly one trips the flag**: `RequestforMediation.docx`,
referenced by nothing, so either dead or resolved dynamically at runtime. That is precisely the kind
of finding this plan exists to surface, and an asset denylist would have erased it silently.

Resolution is a filename lookup against evidence the index already holds (chunk text and
`symbol_refs`); it reads no document contents and adds no parser. That keeps §5's *"do not close the
gap by indexing everything"* rule intact: the file becomes a counted fact with an edge, not a parsed
document. **Membership is by extension** — the office and binary formats listed under Q26 — not by
whether a reference was found, so a zero-reference template stays in the tier and is reported as a
finding rather than falling through to `gap` and being buried under genuinely unparsed source.

**Credential material gets its own line** (`.p12`, `.jks`, `.keystore`, `.pfx`, `.pem`, and by name
`ssTrustStore`, `cacerts`): count and paths only, contents never read or excerpted. `gaps` only says
they exist; `/modernize-assess`'s `SECRETS.local.md` step owns what to do about them.

**Manifest defaults gain `**/legacylift-docs/**`** (Q26), widening the existing
`**/legacylift-docs/index/**`. Verified safe on both corpora: `indexed` is unchanged at 1,229 (NNG)
and 4,715 (ctcm-api), because no file matching `include_globs` lives under it. Without this, the
gap report's largest finding on ctcm-api is LegacyLift's own output.

**The asset and referenced-content extension sets** are, as of Q26:

        asset (excluded-by-design):  .png .jpg .jpeg .gif .psd .ico .bmp .svg
                                     .woff .woff2 .ttf .eot
        referenced content:          .docx .doc .xlsx .xls .pptx .ppt .pdf .zip

Both were fitted to NNG originally and both were wrong on the second corpus; the split above is the
one that holds on both. **Note what did *not* happen here:** the office formats are *not* folded
into the asset globs in the manifest. Suppressing them at the manifest gate would drop them from the
walk entirely and take the referenced-content tier with them — see the caution below.

**Do not push the asset globs into manifest `exclude_globs`.** The original Q12 wording proposed
exactly that, and it is wrong for a reason the tier design makes obvious once measured: the walk
applies manifest `exclude_globs` *first*, so any file suppressed there never reaches tiering at all.
Measured on NNG, adding `**/*.png` and friends to the manifest takes the excluded tier from 89 files
to **0** and the walk total from 1,765 to 1,676 — deleting the very tier §3.D exists to keep visible,
and contradicting "Excluded is not invisible" in the same subsection. The asset and
referenced-content sets are **tier membership rules inside the walk**, not manifest exclusions. The
manifest keeps only `**/legacylift-docs/**`, which is a genuine "never look at this" and has no tier.

### E. Classification data — Q5, Q6, Q11, Q13, Q23

Each gap row carries extension, files, bytes, lines, **linguist language + `type:`**, and **whether a
tree-sitter grammar already exists**. **Two API traps, both verified:**
`detect_language_from_extension` takes the extension **without** a leading dot — `("dtd")` returns
`dtd`, `(".dtd")` returns `None` silently, which would empty the grammar column with no error — and
`has_language()` takes a *language name*, not an extension, so the two are not interchangeable. M0's
pinned-resolution test must cover both. Both are
fact lookups rather than inferences, so PRINCIPLE-1's marking burden is light, and together they are
the triage: `.css` (grammar exists → add a glob) and `.jsp` (no grammar → write an extractor or accept
the gap) are different work items. Content-based inference is out of scope.

The data ships as **derived JSON at `profiles/linguist.json`, no new runtime dependency.** `pyyaml` is
not among the 12 runtime dependencies, and the precedent is exact: `profiles/extractors.json`
(12.5 KB, `schema_version: 1`, loaded at `cli.py:1728` via `Path(__file__).parent / "profiles"`,
already covered by `package-data = ["profiles/*.json"]`). Pruned to `extensions` → `[{name, type,
group}]`, `filenames` → the same, and `vendor.yml`'s regexes. Licence is MIT © GitHub; the attribution
line and the upstream commit SHA live inside the JSON. CLAUDE.md already carries an attribution
convention for the Apache-2.0 `code-modernization` files.

**Extensionless files resolve through linguist's `filenames:` table** (419 entries), not a hand-written
denylist (Q13). Measured: of 82 extensionless files, exactly one is a genuine finding —
`Jenkinsfile` → Groovy / `programming` — while `.project` and `.classpath` → XML / `data`,
`.gitignore` → Ignore List / `data`, and `.keep` / `.checkstyle` / `.pmd` / `.factorypath` stay
unknown. `type:` ranking floats the one real gap above 80 pieces of Eclipse metadata unaided.

**Refresh ritual** (Q23): `tools/legacylift_search/scripts/refresh_linguist.py` — the only place
`pyyaml` is imported — fetches both YAML files and writes the pruned JSON with SHA, fetch date and
attribution. On demand, not scheduled. A test pins a handful of resolutions (`.jsp` → Java Server
Pages / programming, `Jenkinsfile` → Groovy, `.png` → absent) so a bad refresh **fails** rather than
quietly emptying the report. That test is the important half.

### F. Stack prior — Q7

Derived in-process from the index: `SELECT language, COUNT(*), SUM(size_bytes) FROM repo_files GROUP
BY language`. No cross-artifact contract, cannot go stale, and it supplies the byte-weighted
denominator in the same query. **Not** `stats().languages`, which is `SELECT DISTINCT` (`store.py:1047-
1050`) and therefore ranks one stray `.py` equal to 995 `.java` files.

Rejected: a structured `PREFLIGHT.json` (preflight is a prose LLM command, the least reliable link)
and a `stack` field on `domains.json` (authored by assess, which runs after index anyway). Note that
both `/modernize-preflight` Check 1 and `/modernize-assess` Step 2 already *do* stack fingerprinting —
into prose. `domains.json` is the pipeline's only structured artifact and carries no language field.

Enrichment available later from evidence already in the database: `kind LIKE 'hibernate_%'` is "this
is a Hibernate app". **Caution:** the Webflow equivalent does not work — `xml_extractor.py:251-253`
mints state kinds as `el.tag.replace("-", "_")`, so 174 NNG symbols carry bare `view_state` /
`subflow_state` / `decision_state` / `end_state` with no prefix, while `webflow_flow` (`:245`) and every
`hibernate_*` kind are namespaced. Recorded as item 2 of
[`deferred-small-items.md`](./deferred-small-items.md).

### G. Gating and how the number travels — Q8, Q17, Q21

**No gate. Exit 0 always.** A threshold gate would fire on the reference corpus every single run —
NNG sits at 25% after suppression — which is the "teaches people to pass the flag" failure the draft
itself names. The number travels instead of the block: `/modernize-assess` shells out to
`legacylift-search gaps --json` and quotes the headline inline in `ASSESSMENT.md`, at the point where
coverage claims are actually made.

**No new artifact** (Q21). Rejected writing `analysis/$1/GAPS.json`, which would buy a
`/modernize-status` inventory row and a staleness edge. The figure is a cheap measurement — one walk —
so persisting it creates only a staleness liability. `ARCHITECTURE.mmd` earns persistence because it is
an expensive rendering; state this distinction in the plan so the next person does not "fix" it by
adding a file.

**Skill files touched: `modernize-assess.md` only** (Q17), in M4, overwriting its existing CapTech
attribution line (dated 2026-07-24) rather than appending. `/modernize-status` needs no edit and gains
no behaviour; surfacing the percentage in its §4 verdict is recorded as item 1 of
`deferred-small-items.md`.

### H. Output — Q9, Q14, Q24

A `rich` table following `stats`/`coverage`, plus `--json`. Leads with the headline percentage in
**both** raw and post-suppression form, so the suppression is visible rather than silently flattering.

**Bytes and lines both**, counted by the walker itself in one pass over both sides (Q14). Rejected
shelling out to scc (optional tooling, and the allow-list blind spot above) and reusing
`MAX(chunks.end_line)` for the indexed side — that is exact for only 1,173 of 1,229 NNG files, errs
one-sided, and is *total* lines where scc's `Code` column is not, so mixing them would misstate
coverage by ~28%. One identical method on both sides matters more than absolute fidelity, because the
headline is a ratio.

**Truncation follows `store.py:1084-1087`:** the store returns everything, the caller truncates,
totals stay exact over the full set. Display default is top 20 rows per tier with `--limit`; `--json`
is always complete.

### I. Milestones and acceptance — Q16, Q18, Q26

The draft becomes a conforming ExecPlan in five milestones:

- **M0** — vendor `profiles/linguist.json` + refresh script + pinned-resolution test. Pure data.
- **M1** — the walk: five-tier partition, suppression union, line counting. Store-free, unit-testable.
- **M2** — `gaps` command: check one, rich table, `--json`, headline, both modes.
- **M3** — check two (`LEFT JOIN symbols`, `--min-bytes`), and the referenced-content reference
  count, which needs the same index connection.
- **M4** — `**/legacylift-docs/**` in the manifest defaults + `modernize-assess.md` wiring.

M0 and M1 carry no CLI surface, keeping the risky part (vendored data shape) away from the
user-visible contract.

**Acceptance criteria pin the exact numbers, on both corpora** (Q26). Pinning NNG alone is what let
the tier rules ship a 77.9% headline on ctcm-api; one corpus cannot validate a partition whose whole
job is to be right about unfamiliar file types.

**A first-party exclusion applies to both sides of the ratio** (Q27, settled 2026-09-01). The
numerator already has it applied, so applying it to the denominator too is what keeps the headline a
measurement of one population rather than a ratio spanning two. This is §3.H's rule about counting
lines the same way on both sides, restated about *which files* rather than *how they are counted*.
The headline therefore answers: **of the code we said we intend to analyze, what fraction can Layer 0
not see?**

Measured 2026-09-01 under the full settled configuration — manifest `exclude_globs` plus
`**/legacylift-docs/**`, third-party dropped by declared identity and `vendor.yml`'s filename
patterns, first-party excluded as a tier on both sides, `db/**` and `ple-persistence/sql/**` restored:

*NNG* — 72 files / 762 KB third-party dropped, then:

        indexed             871   3301 KB    92232 lines
        gap                 276    804 KB    19637 lines
        first-party excl    482   2669 KB    66580 lines
        asset                60   1344 KB     6873 lines
        referenced content    0      0 KB        0 lines
        credential            4     41 KB      192 lines
        WALK TOTAL         1693   8161 KB   185514 lines

        HEADLINE  19.60% of bytes, 17.55% of lines

with `.jsp` at 178 files / 594 KB / 13,117 lines (74% of the gap by bytes — the real finding),
`.properties` 42, `.vm` 35, and **`nngauthz.tld` and `naesb.tld` present in the gap**, rescued from
the `WEB-INF/tld/**` vendored glob by their declared `nngco.com` identity. Check two returns **5**.

*ctcm-api* — the control: no `knowledge.sqlite`, therefore no first-party list, so this corpus also
exercises predicted mode. 5 files / 92 KB third-party dropped, then 4,715 indexed / **186 gap** / 59
referenced content / 0 asset / 0 credential, tiers summing to **4,960**, a **3.15%-of-bytes and
3.14%-of-lines** headline; the referenced-content tier reports 58 of 59 with at least one indexed
reference and `RequestforMediation.docx` flagged zero-reference; check two returns **0**.

**Pin the reconciliation line too, because it is the thing an implementer will get wrong.** On NNG,
`repo_files` holds 1,229 while the `indexed` tier holds 871; the 358-file difference is the
first-party exclusion, and the report must state it rather than leave someone to diff the two and
file a bug. Observed mode's walk-versus-`repo_files` diff must account for the same 358 instead of
reporting them as discrepancies. On ctcm-api the delta is 0, which is what makes it the useful check
on this logic.

**Every number above is reproducible from a committed script**, not a prose recipe:
[`active/artifacts/gap-detection-probe.py`](../active/artifacts/gap-detection-probe.py), run as
`<venv>/python.exe … gap-detection-probe.py nng --repo <main checkout>`. It prints each corpus's
expected result alongside the measured one, so a disagreement is visible rather than argued. It also
carries the Q27 re-classification of NNG's 45 `domain_exclusions` patterns into vendored and
first-party — without those lists these numbers cannot be reproduced, because the live
`knowledge.sqlite` still holds the un-split original.

A structural assertion ("reports a non-empty gap") would sail past a regression in the exclusion
rules, and a NNG-only assertion sails past everything §2b found. **M4 changes the manifest defaults
and therefore moves these numbers — M4 must restate them.** Note that the asset and
referenced-content tiers are *not* moved by M4, since Q26 keeps their extension sets inside the walk
rather than in the manifest; only `**/legacylift-docs/**` shifts the walk total.

### J. Deferred and spun out

Three measurements taken during the interview became their own drafts rather than parts of this one:
[`durable-loc-counts.md`](./durable-loc-counts.md),
[`embed-everything-evaluation.md`](./embed-everything-evaluation.md), and
[`deferred-small-items.md`](./deferred-small-items.md). One decision (Q25) was implemented instead of
deferred: `/modernize-status` §2 gained a staleness rule comparing the discovery artifacts against the
Layer-0 index and `knowledge.sqlite`, committed with this record.

### K. Exclusion has two axes — Q27

Added 2026-09-01 by the accuracy review. **This supersedes Q4** and settles what §3.D called
"suppression," which named three different mechanisms with one word.

**The two axes.**

- **Third-party — "not this codebase to analyze."** Vendored libraries, published schemas, someone
  else's tag libraries. Not ours, never was. A **drop**: gone from the walk, from the numerator and
  from the denominator. Invisible is correct, because there is nothing for anyone to decide.
- **First-party excluded — "ours, and we chose not to analyze it."** Build config, IDE metadata, CI
  pipelines, and whatever else the people doing the analysis rule out. A **named tier**, counted and
  totalled like the asset tier, because a human decision that shrinks the report must stay auditable.
  This is the `domain-excluded-by-design-tier` move applied one layer out — the same reasoning that
  took NNG's domain coverage from 69% to an honest 100%.

Two questions, cleanly separable: **is it ours?** decides drop-versus-tier; **is it code?** decides
gap-versus-asset. `/modernize-map`'s Jenkinsfile is the worked example — first-party, real, and
relevant to *how the system deploys* rather than to *what it requires*, so it is a first-party
exclusion: present in the tier, absent from the gap, and visibly somebody's decision.

**Third-party provenance is read, not guessed.** `vendor.yml`'s path patterns cannot decide this, and
on NNG they fail in both directions at once:

- **False negative, 29 files.** `vendor.yml` matches **zero** `.tld`, `.xsd` and `.dtd` files in the
  tree, so 14 Spring schemas, 4 Hibernate/W3C DTDs and 9 third-party tag libraries — ~650 KB — would
  be reported as gap findings.
- **False positive, 63 files.** The single pattern `(^|/)[Ee]xtern(als?)?/` claims all of
  `com.nng.ple.{model,service,persistence}.external` — the client's own external-*systems*
  integration layer, including `ContractsService.java`, `LineMasterService.java`,
  `TMSNomConfSchdService.java` and `Contract.hbm.xml`. First-party source, silently deleted.

The formats that carry vendored content **declare their own origin**, and it separates them with no
ambiguity: `.tld` publishes `<uri>`, `.xsd` publishes `targetNamespace`, `.dtd` publishes a PUBLIC
identifier. Measured across all 31 such files on NNG — 29 name `springframework.org`, `java.sun.com`,
`tiles.apache.org`, `joda.org`, `displaytag.sf.net`, Hibernate or the W3C; 2 name `nngco.com`. **A
vendored file names someone else's domain; a first-party one names the client's.** That is a read of
a declared field, the same class of fact as a linguist extension lookup — not an inference — but it
does require opening the file, so **§3.E's "content-based inference is out of scope" is narrowed
here**: it bars *guessing a technology from an extension*, and does not bar reading an identity a
file states about itself.

So: `vendor.yml` contributes its **113 filename/extension patterns** (`jquery*.js`, `prototype.js`,
`.min.js` — precise, and what `config.py:55` already hand-rolls); its **55 directory-shaped patterns
are not adopted**, because that class is where the generic-word collisions live (`external/`,
`cache/`, `env/`, `dist/`, `testdata/`, `deps/` are all ordinary package names). Declared identity
decides the rest. Every dropped file and the rule that dropped it appear in `--json`: 63 files
vanishing without trace is the failure mode; 63 files listed under one named pattern is a
five-second catch.

**Why `domain_exclusions` is not reusable as the first-party list — the provenance finding.** Q4
adopted it for vocabulary reuse. Tracing where it comes from shows the vocabulary is all it shares.
`.claude/skills/code-modernization/commands/modernize-assess.md:170-177` instructs the Step 3
domain-analysis subagent:

> "identify files that are legitimately **not a business capability at all** — tests, ops/DBA and
> build SQL, generated or vendored code — and return a single top-level `exclude_globs` list for
> them… A domain glob always wins over an exclusion (precedence: manual > domain `path_globs` >
> `exclude_globs` > unassigned), **so `exclude_globs` can be generous** — a broad exclusion can never
> hide a file a domain claims."

Three consequences, and none is a defect in `/modernize-assess`, which answers its own question
correctly:

1. **The conflation is authored into the prompt.** One sentence names four unrelated things — tests,
   ops SQL, generated, vendored — and asks for one flat list. For a coverage denominator they are one
   category; for provenance they are not. NNG's 45 patterns are exactly that mixture.
2. **"Can be generous" is an instruction to over-exclude, and its safety net does not travel.** The
   guarantee is that `path_globs` outrank `exclude_globs`. The gap report has no domain globs, so
   nothing outranks anything: the same generous pattern that was provably safe becomes a silent
   delete. `ple-web/src/main/webapp/WEB-INF/tld/**` is that instruction working as designed — it
   catches the 9 vendored tag libraries it was aimed at and takes `nngauthz.tld` and `naesb.tld` with
   them, which cost nothing at the time because coverage did not care whether a file was `excluded`
   or merely untagged.
3. **It is LLM-authored prose config** — the objection §3.F already raised against
   `/modernize-preflight` as a data source, not raised when Q4 adopted this one.

A path-shaped list also cannot express `WEB-INF/tld/`, which is 9/11 vendored and 2/11 first-party in
one flat directory. Provenance is not a property of location.

**The fix, shipped with this record.** `/modernize-assess` now emits **two** lists rather than one.
`exclude_globs` keeps its meaning exactly — first-party, not-a-business-capability, still generous,
still safe because domain `path_globs` outrank it — and a new top-level `vendored_globs` carries
third-party provenance under the opposite instruction: *be conservative, prefer omitting a doubtful
file, because nothing outranks this list.* The prompt names both measured traps: that `external/`,
`cache/` and `env/` are more often application package names than vendor drops, and that a directory
of schemas or `.tld` files usually holds one or two of the client's own, so vendored files should be
named rather than the directory globbed. The agent already makes both judgments; it was being asked
to merge them.

`vendored_globs` is **additive and backwards-compatible**: `DomainsFile` (`domain_tagger.py:92`) sets
no `extra="forbid"`, so pydantic ignores the key — `load_domains_json`, `tag-domains` and the domain
coverage denominator are unaffected, with no `schema_version` bump, no migration and no reindex. M1
adds the field to the model when the walk needs it.

**Provenance precedence, in order** — this is what saves the two first-party `.tld` files from a
vendored glob that is otherwise correct:

1. **Declared identity**, where the format publishes one. Authoritative in both directions: a file
   naming the client's own domain is first-party *even when a `vendored_globs` pattern claims it*.
2. `vendor.yml`'s filename patterns.
3. The assess `vendored_globs` list.
4. Otherwise first-party.

Verified on NNG: rule 1 rescues exactly `nngauthz.tld` and `naesb.tld` from
`ple-web/src/main/webapp/WEB-INF/tld/**`, and nothing else.

**Settled on the NNG list, for the record:** `db/**` and `ple-persistence/sql/**` come out — 25 files
of Quartz cluster DDL, FarmTap backup/rollback and 16 data-cleanup queries that encode real
data-quality rules ("Points Active but missing NNG Rate Zone", "Contacts without Office phones but
required purpose codes"). Those are business rules written in SQL, they are indexed, and four of
check two's eight findings live there.

---

## 4. Decision index

| Q | Decision |
|---|---|
| Q1 | Drop the `include_globs` gate, keep `exclude_globs`; label findings by which gate rejected them |
| Q2 | New `legacylift-search gaps` subcommand — not a `stats` section, not preflight |
| Q3 | Both checks ship together |
| Q4 | Suppress via manifest ∪ domains.json ∪ `vendor.yml`; linguist classifies and ranks, never filters |
| Q5 | Each row carries linguist language + `type:` **and** tree-sitter grammar availability |
| Q6 | Vendor a pinned snapshot with recorded upstream SHA; no runtime fetch, no PyPI dependency |
| Q7 | Stack prior from a weighted `repo_files` GROUP BY — not `stats().languages` |
| Q8 | No gate, exit 0 always; assess quotes the figure instead |
| Q9 | Rich table + `--json`; headline in raw and post-suppression form; store-side truncation discipline |
| Q10 | Check two exposes `--min-bytes`, default 2048 |
| Q11 | Ship derived JSON at `profiles/linguist.json`; no new runtime dependency |
| Q12 | Asset globs into manifest defaults (zero index impact) + a counted excluded-by-design tier |
| Q13 | Extensionless files resolve via linguist `filenames:` |
| Q14 | Walker counts lines itself on both sides; report bytes and lines; no scc |
| Q15 | Credential material gets its own tier — count and paths only, contents never read |
| Q16 | Becomes a conforming ExecPlan in five milestones |
| Q17 | `modernize-assess.md` only; overwrite its existing attribution line |
| Q18 | Acceptance criteria pin exact dated numbers; M4 restates them |
| Q19 | Named `gaps`; `--json` carries `schema_version: 1` |
| Q20 | Observed when an index exists, predicted otherwise; output names the mode |
| Q21 | No new artifact; assess consumes `gaps --json` on stdout |
| Q22 | Mutually exclusive tiers with a fixed precedence, reconciling to the walk total (five as of Q26: `indexed → credential → referenced content → excluded → gap`) |
| Q23 | Refresh script under `scripts/`, on demand, with a pinned-resolution test |
| Q24 | Display top 20 per tier with `--limit`; `--json` always complete |
| Q25 | **Flipped to implement**: `/modernize-status` §2 index-staleness rule, done |
| Q26 | **Added by the accuracy review, 2026-09-01.** A fifth tier, **referenced content**, above excluded: office and binary documents that indexed code resolves *by name*, reported with a per-file reference count and a zero-reference flag. `**/legacylift-docs/**` joins the manifest defaults; the asset and referenced-content extension sets stay **inside the walk**, never in manifest `exclude_globs`. Acceptance pins **both** corpora |
| Q27 | **Added by the accuracy review, 2026-09-01. Supersedes Q4.** Exclusion has two axes: **third-party** ("not this codebase") is a drop, **first-party excluded** ("ours, we chose not to") is a named tier. Third-party provenance is **read from the identity a file declares** (`.tld` `<uri>`, `.xsd` `targetNamespace`, `.dtd` PUBLIC id), not guessed from paths — `vendor.yml` contributes its 113 filename patterns only, never its 55 directory patterns. `domain_exclusions` is **not** reusable as the first-party list as authored |

---

## 5. What must not happen

Carried forward from the draft, all still binding:

**Do not close the gap by indexing everything.** Adding extensions to `_EXTENSION_TO_KEY` — or globs
to `include_globs` — without a parser produces `repo_files` rows with no symbols, moving files from
check one to check two while inflating every coverage denominator. That looks like progress and is
worse than the current state.

**Do not fold this into the semantic-typing pass** (`pending/fact-graph-decision.md` §5a.6 residue
(b), specified at `pending/fact-graph-explanation.md` §9.8). That derives architectural roles over
symbols that already exist; this is about source that produced no symbols at all.

**Do not let it become a blocker on the requirements store.** `active/reqs-to-data-store.md` declares
no dependency here. Its file-level anchor fallback already handles an unparsed citation target safely,
and its `anchor_resolution` rate is the late half of this signal.

Added by the interview:

**Do not use any allow-list as the gap oracle.** scc, linguist and `include_globs` share one failure
mode: each silently omits what it does not recognise. Only a walk that reports the unknown can find
the unknown. Measured cost of forgetting this: scc hides every `.tld`, including NNG's own
`nngauthz.tld` — which declares a custom authorization tag bound to
`com.nng.ple.web.tags.NngAuthorizeTag`, an access-control rule applied across the JSP layer. The
finding is 1.6 KB, not 278 KB (Q27); a real finding does not have to be a large one.

Added by Q27:

**Do not decide provenance from a path.** `WEB-INF/tld/` is 9/11 vendored and 2/11 first-party in one
flat directory; `xmlcatalog/` is 100% vendored by definition; `com/nng/ple/service/external/` is 0%
vendored and `vendor.yml` claims all 63 files of it. Three directories, three different truths. Where
a format declares its own identity, read it.

**Do not reuse an exclusion list authored for another question.** `domain_exclusions` answers "is this
a business capability?" and its prompt says `exclude_globs` "can be generous" — safe there because
domain `path_globs` outrank it, and unsafe here because the gap report has nothing that outranks
anything. A list is only as reusable as the guarantee that justified how it was written.

**Do not let a denylist hide what an allow-list would have hidden.** The rule above about scc cuts
both ways: `domain_exclusions` unioned into the gap report deletes 11 of 13 `.tld`, all 14 `.xsd` and
all 4 `.dtd` — the same files, by the opposite mechanism.

**Do not present an index-derived line count as scc's `Code` figure.** They differ by roughly 28% on
NNG Java.

**Do not let the tiers overlap.** A reader who cannot add the columns to the walk total will not trust
any of them.

**Do not suppress credential material as an asset.** Four files on NNG depend on this.

Added by the accuracy review (Q26):

**Do not suppress a document that code resolves by name.** A `.docx` a controller loads by filename
is one end of a code→content edge; an image is not. Fifty-seven of ctcm-api's 58 templates are bound
to indexed C# by a constants class, and the one that is *not* bound is the finding. Folding them
into the asset bucket erases both facts at once.

**Do not move a tier's membership rules into manifest `exclude_globs`.** The walk applies the
manifest gate before it tiers anything, so a rule placed there deletes the tier instead of
populating it — measured, NNG's excluded tier drops from 89 files to 0. Suppression at the manifest
gate means "never look at this"; tier membership means "we looked, and here is what it is."

**Do not accept a tier rule validated on one corpus.** Every rule in §2 was fitted to NNG and two of
them broke on first contact with ctcm-api, producing a 77.9% headline whose top finding was
LegacyLift's own output. A partition whose job is to be right about unfamiliar file types cannot be
validated against familiar ones.

---

## 6. Next action — DONE 2026-09-01

The rewrite this section called for has happened. `layer0-extraction-gap-detection.md` now lives at
[`active/layer0-extraction-gap-detection.md`](../active/layer0-extraction-gap-detection.md) as a
conforming ExecPlan: §2 and §2b replaced the draft's measurement section, the `.gitignore` sentence
is gone, the cause is re-attributed to `include_globs`, the open questions are the settled design,
and M0–M4 have a Plan of Work, Concrete Steps and acceptance criteria pinning **both** corpora per
Q26. **The next action is M0 of that plan, and it is stated there.**

Three questions this record left open were resolved by the rewrite rather than by the interview, and
their rationale is in that plan's `Decision Log`: where an "own identity" token comes from (a
repeatable `--own-identity`, with declared-identity provenance skipped entirely when none is
supplied, because that fails toward reporting rather than deleting); where the two authored glob
lists are read from (`domains.json` via `--domains`, **not** `knowledge.sqlite`, whose stored list is
still the pre-split mixture §3.K describes); and how the raw pre-suppression headline is defined.

The original text of this section is kept below because the reasoning behind the two closed blockers
is still the audit trail for the acceptance criteria.

**Both blockers the accuracy review opened are now closed by Q27** (§3.K). For the record, what they
were and what the measurements were, since the rewrite's acceptance criteria depend on them:

1. *Is suppression a drop or a tier?* §3.D unioned three sources under one word while §2's
   measurement treated manifest globs as a drop and asset extensions as a tier. Measured with
   `KnowledgeStore.list_exclusions()` unioned in as §3.D specified — and `knowledge.sqlite` exists on
   the reference corpus, so this was the *preferred* observed mode — the walk went 1,765 → 1,126
   files, the gap 443 → 276, the excluded tier 89 → 0, the headline 25.26% → 20.98%, and check two
   **8 → 1**. **Closed by Q27:** two axes, third-party drops and first-party is a named tier.
2. *Do `domains.json` exclusions belong in the union?* **Closed by Q27: no, not as authored** — see
   the provenance finding in §3.K.

**The last sub-decision is settled**: a first-party exclusion applies to **both** sides of the ratio.
Measured under the corrected exclusion split, gap-side-only gives NNG 12.55% of bytes and both-sides
19.60%, over an identical gap tier of 276 files — only the denominator moves, so the choice is about
what "of what?" means, not about what counts as a finding. §3.I now carries the both-sides numbers
for both corpora, re-measured 2026-09-01, along with the `repo_files`-versus-`indexed` reconciliation
that both-sides makes necessary.

**Nothing blocks the rewrite.** The `/modernize-assess` two-list change shipped alongside this record,
and the mechanical corrections the review raised are now fixed at source rather than listed here.
For the record, they were: `include_globs` holds **27** globs, not 31, and five of them are path
patterns rather than extension patterns (§1a — the same error was in `CLAUDE.md`, corrected there in
`139f0af8`); `vendor.yml` holds **168** regexes, not 396, which is its line count (§3.D);
§2's KB column floored each tier and the total independently, so it summed to 8,921 against a stated
8,923 while claiming "tiers sum exactly" (§2, now rounded consistently, with both counting
conventions stated); `list_exclusions()` is called at `cli.py:310` and `indexer.py:1003`, not
`cli.py:272` / `indexer.py:921` (§1e); the truncation discipline is documented at
`store.py:1084-1087`, not `1064-1065` (§3.H); and `detect_language_from_extension` takes the
extension **without** a leading dot while `has_language()` takes a language name, not an extension
(§3.E).

**What that list is worth reading for.** Five of the six were in *interfaces* — a line number, an
argument convention, a rounding rule at a column boundary — which is where the reqs-to-data-store
plan's ninth review round found its blockers clustered too. None was found by re-reading the prose;
each needed the thing itself opened. The two findings that changed the design (Q26, Q27) came the
same way: running the rules against a second corpus, and asking where a list came from.
