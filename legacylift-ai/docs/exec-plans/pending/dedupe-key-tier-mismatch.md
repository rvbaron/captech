# Draft: the dedupe key's tiered discriminator cannot match a body-carrying row to a bodyless one

**Status: PENDING — measured, not started. Needs a design decision, and it is no longer a free
change.** Filed 2026-09-10 from Step 10 Phase 3 of
[`active/reqs-to-data-store.md`](../active/reqs-to-data-store.md), whose
`Outcomes & Retrospective` → *Step 10 Phase 3, as measured* is the definitive record of the
measurement. This file exists because the fix needs a design conversation, which
`pending/deferred-small-items.md`'s own entry bar says disqualifies it from that list.

---

## The defect

`dedupe_key` hashes a **tiered** discriminator (`gr_keys.py:13` and the docstring below it):

    dedupe_key             = "dk1:"  + sha256(anchors ␟ rule_class ␟ pattern ␟ discriminator)[:16]
    dedupe_key_anchor_only = "dka1:" + sha256(anchors ␟ rule_class ␟ pattern)[:16]

with the discriminator selected per row by `select_discriminator`: **tier 1** the canonical form of
the structured body, **tier 2** the sorted span-level `content_hash` set from the citations, **tier
3** the empty string.

The tier is chosen from **one row's own contents**, and the key is then compared by equality. So
when the same rule is mined twice and the extractor emits a `structuredBody` on one pass and not the
other, the two rows are discriminated **at different tiers** — one hashes a body, the other hashes a
span set — and **their `dedupe_key`s cannot be equal no matter how identical the rule is.** Stage
one's exact-key merge is structurally unreachable for that pair.

## The measurement

On the 437-rule four-round NNG corpus, first ingest into an empty store
(`RUN-01M2646H97JAZJPPKHSCZT1RRY`, 379 rows):

| figure | value |
|---|---|
| distinct `dedupe_key` over 379 rows | **379** — every row unique |
| distinct `dedupe_key_anchor_only` | **325** |
| anchor-only clusters holding more than one row | **34** |
| excess rows in those clusters | **54** (14.2% of the store) |
| …of which **mixed** — some rows carry a body, some do not | **18 of 34** |
| …all rows carry a body, split on differing body text | 7 of 34 |
| …no row carries a body, split on differing span sets | 9 of 34 |
| rows carrying any `structured_body` | **88 of 379 (23.2%)** |

The clearest instance is `ple-services/JavaSource/com/nng/ple/service/StatusHistoryService.java:151-167`,
where **four** rows share one `dka1:e3485b145836401a`, one anchor, one subject, one `rule_class` and
one `pattern`: one row has no body, and three carry `invariant` bodies of 301 / 267 / 255
characters. Their names are "Active status coverage is judged without checking for gaps", "Coverage
by active status periods", "Active status coverage of a dated record" and "Active coverage of a term
by status periods" — one rule, four rows.

**The cleanest proof case, found 2026-09-10 by Phase 5's threshold harness.** Exactly one pair of
requirements in the store shares a **byte-identical `statement`**, and they are two rows at vector
distance **0.0000**:

| | `4A85JX` | `2ST1MQ` |
|---|---|---|
| `statement` | "An Active point status period never carries a termination type." | *identical* |
| `rule_class` / `pattern` | `definitional` / `D-IMPOSS` | *identical* |
| `dedupe_key_anchor_only` | `dka1:e07a328170b234d3` | *identical* |
| citation | `PoipointService.java:928-931` | *identical* |
| span `content_hash` | `ch1:2578ba85` | *identical* |
| `structured_body` | **none** → tier 2, hashes `ch1:2578ba85` | **`invariant`, 185 chars** → tier 1, hashes the body |
| `dedupe_key` | `dk1:bfab427f58937e15` | `dk1:873a2386c9cc516c` |

**Every input a tier-2 key would take is identical, and the rows still did not merge.** Had both
been discriminated at tier 2 their keys would have been byte-equal. The tier choice alone caused the
split — which is the whole claim of this draft, on a pair where nothing else can be blamed. Queued
as `drift`, so the safety net held here too. **Write the regression test against this pair.**

**Body emission is what varies, and nothing measures its stability.** 23.2% of rows carry a body, so
across four rounds a re-mined rule has a substantial chance of landing on both sides of the tier
split. This bounds the exact key's hit rate by a property of the extractor's output that no
acceptance check covers.

## Why it is not urgent, and must not be sold as a bug

**The safety net was verified, not assumed.** Every internal pair of all **34** clusters is queued in
`gr_merge_candidate` as a `drift` candidate — **34/34, 0 partial, 0 missed**, all
`resolution='unresolved'`. That is exactly the asymmetry `gr_ingest.py`'s docstring argues for: a
false-distinct is *visible* and a reviewer merges it; a false-same is *invisible* and loses a rule
forever, so the exact key is deliberately biased toward under-merging and stage two recovers the
residue. **On this corpus the design's own argument held.** The cost of the defect is therefore
reviewer time on 54 rows, not lost coverage.

So this is a **precision** improvement to an intentionally conservative key — not a correctness
fix. Anyone picking it up should be able to say why the current behaviour is defensible before
proposing to change it.

## Why it is no longer a free change

**The store is populated as of 2026-09-10.** Before Phase 3 the key could have been altered by
editing `gr_keys.py` and re-ingesting. Now `knowledge.sqlite` holds 379 rows whose `dedupe_key` and
`dedupe_key_anchor_only` are stored **columns**, 148 `gr_merge_candidate` rows keyed on
requirement pairs, and 437 `gr_run_hit` rows recording which offer landed where. Changing the key
formula means a **re-key migration** that recomputes both columns for every row — and any re-key
that would now collapse two existing rows has to decide what happens to their citations, scenarios,
edge cases, findings, vectors and the candidate pairs naming them. That is the design conversation.

Note also that entry 9 of `pending/deferred-small-items.md` ("A JSP extractor would re-key every
rule that cites a JSP") is the *same class of problem from a different direction*, and entry 12
concerns the same ingest's reporting. Whoever opens the re-key question should read both.

## Open questions

1. **Match on either key, or change the key?** The narrowest fix leaves `dedupe_key` alone and adds
   a **tier-2-only** key computed for *every* row (body-carrying rows included), so stage one can
   try exact → tier-2-equal → anchor-only. That adds a column instead of redefining one, so no
   existing key changes meaning and the migration is a backfill rather than a re-key. It is probably
   the right shape, and it should still be argued rather than assumed.
2. **If a tier-2-only key is added, is a hit on it an auto-merge or a candidate?** A tier-2 match
   means identical anchors, class, pattern *and* identical cited bytes. That is a strong claim of
   sameness — but auto-merging on it moves a population of 54 rows out of the reviewer's queue and
   into invisibility, which is precisely the trade the design refuses elsewhere.
3. **What about the 7 all-body clusters?** Their bodies differ textually for the same rule, so no
   tier-1 canonicalization short of semantic comparison will match them. Are they simply the drift
   queue's permanent job?
4. **And the 9 bodyless clusters?** They split because span sets differ within one symbol anchor —
   two agents citing different line ranges of the same method. Arguably correct behaviour, since
   different lines may really be different rules. Needs a look at the 9 before deciding.
5. **Should body emission be stabilized instead, or as well?** If the extractor emitted a body for
   every rule of a body-eligible type, the mixed case would largely disappear at the source. That is
   a prompt change in `extract-rules.js`, not a store change, and it interacts with
   `pending/dto-catalog-bounding.md`'s work on the same file.

## Would touch

- `tools/legacylift_search/src/legacylift_search/gr_keys.py` — `select_discriminator`,
  `compute_dedupe_keys`, and the module docstring, which is the authority on the formula and would
  have to state the new one.
- `tools/legacylift_search/src/legacylift_search/gr_ingest.py` — stage one's lookup order, and the
  docstring's account of the two-stage merge.
- `gr_fields.py` / `read_cmds.py` — a new key column is store-written, so it belongs in the
  store-owned field list rather than the extractor-owned one.
- A versioned migration under Milestone 0's machinery, plus the backfill.
- Tests: the natural regression case is the four-row `StatusHistoryService.java:151-167` cluster,
  which is reproducible from the saved corpus at
  `analysis/customer.ple.nng.app/knowledge/extracted-rules-4round.json` (**untracked and
  unreproducible — never overwrite it**).
